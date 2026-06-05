"""Derive analysis-ready measures + the NA-with-reason coverage ledger.

Runs on one speaker's merged frame (the output of merge_metadata, which still carries
load_extraction's `f0_contour`, `has_<landmark>`, and `accepted` columns). Adds the few
measures the frozen Praat battery deliberately leaves to analysis, and emits an explicit
per-(token, measure) verdict so nothing is ever silently dropped. Never edits raw measures,
never drops rows.

Three derived columns - the only things that combine/reproject raw measures:
  f0_mid_hz             vowel-body f0: NaN-aware median of the contour's central third.
  f0_onset_excursion_st 12*log2(f0_onset / f0_mid). Semitones of onset f0 above the vowel
                        body; POSITIVE = raised onset (the ejective f0 signature). Within-
                        token, no cross-speaker baseline (fits n=2, per-speaker analysis).
  silent_gap_ms         t_glot_rel - t_burst (= -glottal_oral_ms): the post-burst, sealed-
                        glottis silence of an ejective. Ejectives only.

Coverage ledger - every measure x every token classified as exactly one of:
  present   the measure applies and a value was measured.
  n/a       the measure does not apply to this token by linguistic design (landmark/
            property absent on purpose, e.g. closure for a word-initial stop). Carries the
            reason.
  missing   the measure DOES apply but the value is NaN - a real annotation/measurement gap
            worth chasing. Carries the reason. This is the scientifically actionable bucket.
"""

import numpy as np
import pandas as pd

# The measure columns analysis cares about (raw battery measures + the 3 derived ones).
# Excludes ids, landmark times, the f0 contour string, and the dup/order quality flags
# (those are validate's job, not measures).
ALL_MEASURES = [
    # temporal
    "vot_ms", "closure_dur_ms", "glottal_oral_ms", "vowel_dur_ms",
    "voiced_closure_prop", "voiced_closure_onset_ms",
    # intensity
    "burst_intensity_db", "vowel_onset_intensity_db", "burst_vowel_ratio_db",
    "noise_intensity_db", "noise_is_silent",
    # spectral moments of the burst->voicing noise window
    "noise_cog_hz", "noise_sd_hz", "noise_skew", "noise_kurt",
    # formants
    "f1_onset_hz", "f2_onset_hz", "f3_onset_hz", "f1_mid_hz", "f2_mid_hz", "f3_mid_hz",
    # f0 / phonation / perturbation
    "f0_onset_hz", "h1_h2_db", "hnr_db", "jitter_local", "shimmer_local",
    # derived
    "f0_mid_hz", "f0_onset_excursion_st", "silent_gap_ms",
]

DERIVED_COLS = ["f0_mid_hz", "f0_onset_excursion_st", "silent_gap_ms"]

# Coverage spec: which measures are CONDITIONALLY applicable (can be 'n/a' by design).
# Everything else in ALL_MEASURES is "always expected" - present if measured, else 'missing'.
CLOSURE_MEASURES = ["closure_dur_ms", "voiced_closure_prop", "voiced_closure_onset_ms"]
EJECTIVE_MEASURES = ["glottal_oral_ms", "silent_gap_ms"]
# canonical formants come from the FastTrack join; a NaN here distinguishes "whole FastTrack
# row absent" (token_id drift / pass not run) from "value unmeasurable" via ft_ceiling_hz.
FT_FORMANT_MEASURES = ["f1_onset_hz", "f2_onset_hz", "f3_onset_hz",
                       "f1_mid_hz", "f2_mid_hz", "f3_mid_hz"]


def _central_third(arr):
    """NaN-aware median of the central third of a 1-D array; nan if no finite samples.

    Trims n//3 samples off each end (the steady-state vowel body), avoiding onset/offset
    perturbation. For a 3-sample contour this is just the middle sample.
    """
    a = np.asarray(arr, dtype=float).ravel()
    n = a.size
    if n == 0:
        return np.nan
    lo = n // 3
    core = a[lo:n - lo] if n - lo > lo else a
    core = core[np.isfinite(core)]
    return float(np.median(core)) if core.size else np.nan


def add_derived(merged):
    """Return a copy of the merged frame with the 3 derived columns appended."""
    df = merged.copy()

    contour = df["f0_contour"] if "f0_contour" in df.columns else pd.Series(
        [np.array([], dtype=float)] * len(df), index=df.index
    )
    df["f0_mid_hz"] = contour.map(_central_third)

    onset = pd.to_numeric(df.get("f0_onset_hz"), errors="coerce")
    mid = pd.to_numeric(df["f0_mid_hz"], errors="coerce")
    ok = onset.notna() & mid.notna() & (onset > 0) & (mid > 0)
    exc = pd.Series(np.nan, index=df.index, dtype=float)
    exc.loc[ok] = 12.0 * np.log2(onset[ok].to_numpy() / mid[ok].to_numpy())
    df["f0_onset_excursion_st"] = exc

    # silent gap = oral release -> glottal release silence = t_glot_rel - t_burst = -glottal_oral_ms.
    # Non-ejectives have no glottal_oral_ms (NaN) -> silent_gap stays NaN.
    df["silent_gap_ms"] = -pd.to_numeric(df.get("glottal_oral_ms"), errors="coerce")

    return df


def _col(df, name):
    """A row-aligned Series for an optional metadata column (all-NA if absent)."""
    if name in df.columns:
        return df[name]
    return pd.Series([pd.NA] * len(df), index=df.index)


def build_coverage(df):
    """Long coverage ledger: one row per (token_id, measure) with status + reason.

    status in {present, n/a, missing}; reason is "" for present.
    """
    n = len(df)
    manner = _col(df, "manner")
    position = _col(df, "position")
    category = _col(df, "category")

    is_ejective = category.fillna("").astype(str).str.endswith("_ejective")
    is_fricative = manner.eq("fricative")
    is_stop_aff = manner.isin(["stop", "affricate"])
    is_initial = position.eq("initial")
    is_interv = position.eq("intervocalic")

    # closure measures: applicable only to a stop/affricate that HAS a closure (intervocalic).
    closure_expected = (is_stop_aff & is_interv).to_numpy()
    closure_na = np.select(
        [is_fricative.to_numpy(), is_initial.to_numpy()],
        ["no closure (fricative)", "no closure (word-initial)"],
        default="no closure (position/manner unknown)",
    )
    closure_missing = "intervocalic stop/affricate: t_clo not marked"

    # glottal/ejective measures: applicable only to ejectives.
    ej_expected = is_ejective.to_numpy()
    ej_na = "not an ejective"
    ej_missing = "ejective: t_glot_rel/t_burst not marked"

    # FastTrack formants: a NaN ft_ceiling_hz means the whole formant row never arrived.
    ft_absent = _col(df, "ft_ceiling_hz").isna().to_numpy()

    tokens = df["token_id"].to_numpy()
    frames = []
    for m in ALL_MEASURES:
        if m not in df.columns:
            continue
        if m in CLOSURE_MEASURES:
            expected, na_reason, missing_reason = closure_expected, closure_na, closure_missing
        elif m in EJECTIVE_MEASURES:
            expected, na_reason, missing_reason = ej_expected, ej_na, ej_missing
        elif m in FT_FORMANT_MEASURES:
            expected, na_reason = True, None
            missing_reason = np.where(
                ft_absent, "no FastTrack formant row (token absent from formants CSV)",
                f"{m}: FastTrack formant NA (unmeasurable)",
            )
        else:
            expected, na_reason, missing_reason = True, None, f"{m}: applicable but value NA (unmeasurable)"

        present = df[m].notna().to_numpy()
        exp = expected if isinstance(expected, np.ndarray) else np.full(n, bool(expected))
        na_arr = np.full(n, "") if na_reason is None else (
            na_reason if isinstance(na_reason, np.ndarray) else np.full(n, na_reason)
        )
        miss_arr = missing_reason if isinstance(missing_reason, np.ndarray) else np.full(n, missing_reason)

        status = np.where(present, "present", np.where(exp, "missing", "n/a"))
        reason = np.where(present, "", np.where(exp, miss_arr, na_arr))
        frames.append(pd.DataFrame(
            {"token_id": tokens, "measure": m, "status": status, "reason": reason}
        ))

    coverage = pd.concat(frames, ignore_index=True)
    return coverage.sort_values(["token_id", "measure"]).reset_index(drop=True)


def derive(merged, config=None):
    """Add derived columns and build the coverage ledger.

    Returns (derived_frame, coverage_long). `config` is accepted for symmetry with the rest
    of the pipeline but is unused (the central-third trim is fixed, no knob needed yet).
    """
    derived = add_derived(merged)
    coverage = build_coverage(derived)
    return derived, coverage
