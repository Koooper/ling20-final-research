"""The audit gate. Sanity assertions over the merged frame + the wiring contracts.

Hard failures (structural breakage) raise ValidationError; soft issues are collected as
warnings and reported, never silently dropped. Range/tolerance numbers come from
config.validation. This runs on committed landmarks only - it never edits the data.
"""

import pandas as pd

HARD = "error"
SOFT = "warning"


class ValidationError(Exception):
    pass


class ValidationReport:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = {}

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    @property
    def ok(self):
        return not self.errors

    def text(self):
        lines = []
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            lines += [f"  - {m}" for m in self.errors]
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            lines += [f"  - {m}" for m in self.warnings]
        for k, val in self.info.items():
            lines.append(f"{k}: {val}")
        if not lines:
            lines.append("clean: no errors, no warnings")
        return "\n".join(lines)


def _accepted_mask(df):
    return df["accepted"] if "accepted" in df.columns else (df["status"] == "accepted")


def validate(merged, config, merge_report=None, formant_report=None, *, raise_on_error=True):
    """Validate the merged frame. Returns a ValidationReport; raises on hard errors."""
    rep = ValidationReport()
    v = config.validation
    df = merged

    # ---- HARD: duplicate token_id (the join key must be unique) ----
    dups = df["token_id"][df["token_id"].duplicated(keep=False)]
    if len(dups):
        rep.error(f"duplicate token_id: {sorted(dups.unique().tolist())}")

    # ---- HARD/SOFT: merge orphans ----
    if merge_report:
        if merge_report.get("orphans_no_manifest"):
            rep.error(
                "file stem(s) with no manifest row (slice/measurement mismatch): "
                f"{merge_report['orphans_no_manifest']}"
            )
        for tid in merge_report.get("orphans_no_metadata", []):
            rep.warn(f"{tid}: word has no words_metadata row (not authored yet?)")
        for w in merge_report.get("unused_metadata_words", []):
            rep.warn(f"metadata word never measured: {w!r}")

    # ---- SOFT: FastTrack formant join health ----
    if formant_report:
        if formant_report.get("absent"):
            rep.warn("no FastTrack formants joined (02b_formants.praat not run yet?) - "
                     "canonical formants are all NA")
        for tid in formant_report.get("formant_orphans", []):
            rep.warn(f"formant row with no measurement token (token_id drift?): {tid}")
        if not formant_report.get("absent"):
            acc_no_ft = [
                t for t in formant_report.get("tokens_without_formant", [])
                if t in set(df.loc[_accepted_mask(df), "token_id"])
            ]
            if acc_no_ft:
                rep.warn(f"{len(acc_no_ft)} accepted token(s) have no FastTrack formant row "
                         f"(e.g. {acc_no_ft[:3]})")

    # ---- SOFT: FastTrack per-token diagnostics ----
    if "ft_ceiling_at_bound" in df.columns:
        m = df["ft_ceiling_at_bound"] == 1
        for tid in df.loc[m, "token_id"]:
            rep.warn(f"{tid}: FastTrack winning ceiling hit the range edge (widen ft_low/ft_high?)")
    if "ft_minerror" in df.columns and "ft_minerror_max" in v:
        m = df["ft_minerror"].notna() & (df["ft_minerror"] > v["ft_minerror_max"])
        for tid, val in zip(df.loc[m, "token_id"], df.loc[m, "ft_minerror"]):
            rep.warn(f"{tid}: FastTrack winner error {val} > {v['ft_minerror_max']} "
                     "(heuristic penalty? bad track - check the comparison image)")

    # ---- SOFT: numeric ranges ----
    def rng(col, key):
        if col in df.columns and key in v:
            lo, hi = v[key]
            m = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
            for tid, val in zip(df.loc[m, "token_id"], df.loc[m, col]):
                rep.warn(f"{tid}: {col}={val} outside [{lo}, {hi}]")

    rng("vot_ms", "vot_range_ms")
    rng("closure_dur_ms", "closure_dur_range_ms")
    rng("noise_cog_hz", "cog_range_hz")
    for suf in ("onset", "mid"):
        rng(f"f1_{suf}_hz", "f1_range_hz")
        rng(f"f2_{suf}_hz", "f2_range_hz")
        rng(f"f3_{suf}_hz", "f3_range_hz")

    # ---- SOFT: formant ordering F1 < F2 < F3 ----
    for suf in ("onset", "mid"):
        f1, f2, f3 = f"f1_{suf}_hz", f"f2_{suf}_hz", f"f3_{suf}_hz"
        if all(c in df.columns for c in (f1, f2, f3)):
            present = df[f1].notna() & df[f2].notna() & df[f3].notna()
            bad = present & ~((df[f1] < df[f2]) & (df[f2] < df[f3]))
            for tid in df.loc[bad, "token_id"]:
                rep.warn(f"{tid}: formants not ordered F1<F2<F3 ({suf})")

    # ---- SOFT: non-negative durations ----
    for col in ("closure_dur_ms", "vowel_dur_ms"):
        if col in df.columns:
            m = df[col].notna() & (df[col] < 0)
            for tid, val in zip(df.loc[m, "token_id"], df.loc[m, col]):
                rep.warn(f"{tid}: {col}={val} is negative")

    # ---- SOFT: landmark time ordering t_clo < t_burst < t_voi < t_vend ----
    order_cols = ["t_clo_s", "t_burst_s", "t_voi_s", "t_vend_s"]
    if all(c in df.columns for c in order_cols):
        for _, r in df.iterrows():
            times = [r[c] for c in order_cols if pd.notna(r[c])]
            if any(times[i] > times[i + 1] for i in range(len(times) - 1)):
                rep.warn(f"{r['token_id']}: landmark times out of order")

    # ---- SOFT: surface 02's own dup/order flags ----
    for col, what in (("dup_flag", "duplicate landmark"), ("order_flag", "landmark order")):
        if col in df.columns:
            for tid in df.loc[df[col] == 1, "token_id"]:
                rep.warn(f"{tid}: 02 set {col} ({what})")

    # ---- SOFT: >1 target segment per word file ----
    if "segment_label" in df.columns:
        for tid, seg in zip(df["token_id"], df["segment_label"]):
            if pd.notna(seg) and seg != "s1":
                rep.warn(f"{tid}: segment '{seg}' (>1 target/word; word-grain metadata can't disambiguate)")

    # ---- SOFT: sound_type (Praat) vs category (metadata) cross-check ----
    if "sound_type" in df.columns and "category" in df.columns:
        m = df["sound_type"].notna() & df["category"].notna() & (df["sound_type"] != df["category"])
        for tid, st, cat in zip(df.loc[m, "token_id"], df.loc[m, "sound_type"], df.loc[m, "category"]):
            rep.warn(f"{tid}: sound_type '{st}' != metadata category '{cat}'")

    # ---- SOFT: thin categories ----
    if "category" in df.columns and "min_tokens_per_category" in v:
        acc = df[_accepted_mask(df)]
        counts = acc["category"].dropna().value_counts()
        for cat, n in counts.items():
            if n < v["min_tokens_per_category"]:
                rep.warn(f"category '{cat}': {n} accepted token(s) (< min {v['min_tokens_per_category']})")
        rep.info["category_counts"] = counts.to_dict()

    rep.info["status_counts"] = df["status"].value_counts(dropna=False).to_dict()

    if raise_on_error and rep.errors:
        raise ValidationError("validation failed:\n  - " + "\n  - ".join(rep.errors))
    return rep
