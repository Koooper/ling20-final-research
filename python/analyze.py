"""Property-dispatch analysis views over one speaker's derived frame.

Every token lives in a single `full_inventory`; each research question is a NON-EXCLUSIVE
VIEW that selects by linguistic property and groups by linguistic property. A token feeds
every view it qualifies for. Operates on ONE speaker's frame - run_pipeline loops speakers,
and the two are NEVER pooled. Only `accepted` tokens are summarized.

Each view emits a long-format summary table: one row per (group x measure) carrying the
descriptive stats over present values PLUS the coverage accounting (n_present / n_na /
n_missing / na_reasons) pulled from derive's ledger, so a thin or empty cell explains itself.

Degrade-to-ungrouped: if a group_by column is entirely NA in the selected rows (true today
for `following_vowel` and `stress`, both unfilled in words_metadata.csv) it is dropped from
the grouping and noted - tokens are never dropped. A view whose group keys are all empty
collapses to a single `_all_` bucket.
"""

import numpy as np
import pandas as pd

try:                                  # works as a package module or flat on sys.path
    from python.derive import ALL_MEASURES
except ImportError:                   # pragma: no cover
    from derive import ALL_MEASURES

SUMMARY_COLS = [
    "measure", "n", "n_present", "n_na", "n_missing", "na_reasons",
    "mean", "median", "sd", "min", "max",
]


class View:
    """A non-exclusive lens: select rows by property, group by property, summarize measures."""

    def __init__(self, name, select, group_by, measures):
        self.name = name
        self.select = select          # df -> boolean Series
        self.group_by = group_by      # list of property columns
        self.measures = measures      # list of measure columns


def build_views():
    """The five views. burst_vowel_ratio_db in q4 IS the 'burst_intensity_rel' of the RQ."""
    return [
        View(
            "full_inventory",
            lambda d: pd.Series(True, index=d.index),
            ["category", "place", "position"],
            list(ALL_MEASURES),
        ),
        View(  # Q1 - plain stop realization + aspiration contrast
            "q1_stops",
            lambda d: d["manner"].eq("stop"),
            ["laryngeal", "place", "position"],
            ["vot_ms", "voiced_closure_prop", "closure_dur_ms", "voiced_closure_onset_ms"],
        ),
        View(  # Q2 - guttural (uvular vs glottal) aspiration localization
            "q2_guttural",
            lambda d: d["laryngeal"].isin(["aspirated_uvular", "aspirated_glottal"]),
            # laryngeal must lead the grouping or the uvular vs glottal series pool together
            # and the contrast Q2 measures vanishes; following_vowel adds vowel context.
            ["laryngeal", "place", "following_vowel"],
            ["noise_cog_hz", "noise_sd_hz", "noise_skew", "noise_kurt"],
        ),
        View(  # Q3 - affricate differentiation
            "q3_affricate",
            lambda d: d["manner"].eq("affricate"),
            ["laryngeal"],
            ["vot_ms", "silent_gap_ms", "noise_cog_hz", "noise_sd_hz", "noise_skew", "noise_kurt"],
        ),
        View(  # Q4 - ejective canonicality
            "q4_ejective",
            lambda d: d["laryngeal"].eq("ejective"),
            ["manner", "place"],
            ["silent_gap_ms", "burst_vowel_ratio_db", "f0_onset_hz", "f0_onset_excursion_st",
             "h1_h2_db", "hnr_db", "jitter_local", "shimmer_local"],
        ),
    ]


def _accepted(df):
    if "accepted" in df.columns:
        return df["accepted"].fillna(False).astype(bool)
    return df["status"].eq("accepted")


def _has_values(s):
    """True if a grouping column carries any real value. Blank cells arrive as "" (the CSV
    readers use keep_default_na=False), so treat empty/whitespace strings as absent too -
    this is what makes an unfilled column (following_vowel, stress) degrade out of grouping."""
    vals = s.dropna().astype(str).str.strip()
    return (vals != "").any()


def _round(x):
    return round(float(x), 3) if pd.notna(x) else np.nan


def _describe(gb, keyvals, measure, group, coverage, token_ids):
    """One summary row: stats over present values + coverage accounting for this cell."""
    vals = pd.to_numeric(group[measure], errors="coerce") if measure in group.columns else pd.Series([], dtype=float)
    present = vals.dropna()
    cov = coverage[(coverage["measure"] == measure) & (coverage["token_id"].isin(token_ids))]
    non_present = cov[cov["status"] != "present"]["reason"]
    na_reasons = "; ".join(f"{r} (x{c})" for r, c in non_present.value_counts().items())

    row = {gb[i]: keyvals[i] for i in range(len(gb))}
    row.update({
        "measure": measure,
        "n": len(group),
        "n_present": int((cov["status"] == "present").sum()),
        "n_na": int((cov["status"] == "n/a").sum()),
        "n_missing": int((cov["status"] == "missing").sum()),
        "na_reasons": na_reasons,
        "mean": _round(present.mean()) if len(present) else np.nan,
        "median": _round(present.median()) if len(present) else np.nan,
        "sd": _round(present.std(ddof=1)) if len(present) > 1 else np.nan,
        "min": _round(present.min()) if len(present) else np.nan,
        "max": _round(present.max()) if len(present) else np.nan,
    })
    return row


def summarize_view(view, df, coverage):
    """Return (summary_df, notes). notes carries selection size + which group keys degraded."""
    mask = view.select(df)
    mask = mask.fillna(False).astype(bool) & _accepted(df)
    sel = df[mask]

    gb = [c for c in view.group_by if c in sel.columns and _has_values(sel[c])]
    dropped = [c for c in view.group_by if c not in gb]
    notes = {"n_selected": int(len(sel)), "group_by": gb, "dropped_group_keys": dropped}

    if len(sel) == 0:
        return pd.DataFrame(columns=gb + SUMMARY_COLS), notes

    if gb:
        iterator = sel.groupby(gb, dropna=False, sort=True)
        groups = [(k if isinstance(k, tuple) else (k,), g) for k, g in iterator]
    else:
        groups = [(("_all_",), sel)]
        gb = ["group"]

    rows = []
    for keyvals, g in groups:
        token_ids = set(g["token_id"])
        for m in view.measures:
            rows.append(_describe(gb, keyvals, m, g, coverage, token_ids))

    summary = pd.DataFrame(rows).sort_values(gb + ["measure"], na_position="last").reset_index(drop=True)
    return summary, notes


def formant_method_comparison(frame):
    """Single-ceiling (sc_) vs FastTrack (canonical) formants over accepted tokens.

    A methods artifact: per formant slot, how far the FastTrack winner moved the value off the
    single-ceiling estimate. One row per slot; only tokens where BOTH are present are compared.
    """
    acc = frame[_accepted(frame)]

    def col(name):
        return pd.to_numeric(acc[name], errors="coerce") if name in acc.columns else pd.Series(
            [pd.NA] * len(acc), index=acc.index, dtype="float64"
        )

    rows = []
    for slot in ("f1_onset", "f2_onset", "f3_onset", "f1_mid", "f2_mid", "f3_mid"):
        can, sc = col(slot + "_hz"), col("sc_" + slot + "_hz")
        both = can.notna() & sc.notna()
        diff = (can - sc)[both]
        rows.append({
            "measure": slot + "_hz",
            "n": int(both.sum()),
            "canonical_mean": _round(can[both].mean()) if both.any() else np.nan,
            "sc_mean": _round(sc[both].mean()) if both.any() else np.nan,
            "mean_abs_diff_hz": _round(diff.abs().mean()) if both.any() else np.nan,
            "mean_signed_diff_hz": _round(diff.mean()) if both.any() else np.nan,
            "max_abs_diff_hz": _round(diff.abs().max()) if both.any() else np.nan,
        })
    return pd.DataFrame(rows)


def analyze(derived, coverage, config=None):
    """Run every view. Returns {view_name: summary_df}.

    `config` is accepted for pipeline symmetry (unused for now). Referenced property columns
    that are missing from the frame are added as all-NA so selects/groupings never KeyError.
    """
    views = build_views()
    needed = {"manner", "laryngeal", "place", "category", "position"}
    for v in views:
        needed |= set(v.group_by)

    d = derived.copy()
    for c in needed:
        if c not in d.columns:
            d[c] = pd.NA

    return {v.name: summarize_view(v, d, coverage)[0] for v in views}
