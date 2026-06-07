"""Load a measurements_{speaker}.csv (the frozen, identity-blind Praat extraction).

Responsibilities: assert the column schema (a contract test - fails loud if 02 drifts),
turn Praat's "NA" sentinel into real NaN, coerce numerics, parse the f0 contour string,
and add per-row landmark-availability flags. Does NOT drop rows by status - it tags them
so validate/analysis can decide and count what was excluded.
"""

import numpy as np
import pandas as pd

# The frozen schema, in order, exactly as 02_extract_measurements.praat writes it.
# A mismatch here means the Praat script and the Python pipeline have drifted apart.
EXTRACTION_COLUMNS = [
    "file",
    "token_id",
    "speaker",
    "rep_label",
    "segment_label",
    "sound_type",
    "status",
    "seg_start_s",
    "seg_end_s",
    "t_clo_s",
    "t_burst_s",
    "t_voi_s",
    "t_vend_s",
    "t_glot_rel_s",
    "t_pvend_s",
    "vot_ms",
    "closure_dur_ms",
    "glottal_oral_ms",
    "vowel_dur_ms",
    "voiced_closure_prop",
    "voiced_closure_onset_ms",
    "burst_intensity_db",
    "vowel_onset_intensity_db",
    "burst_vowel_ratio_db",
    "noise_intensity_db",
    "noise_is_silent",
    "noise_cog_hz",
    "noise_sd_hz",
    "noise_skew",
    "noise_kurt",
    # single-ceiling formants (co-compat); FastTrack canonical f1_onset_hz/... join in by token_id
    "sc_f1_onset_hz",
    "sc_f2_onset_hz",
    "sc_f3_onset_hz",
    "sc_f1_mid_hz",
    "sc_f2_mid_hz",
    "sc_f3_mid_hz",
    "f0_onset_hz",
    "h1_h2_db",
    "hnr_db",
    "jitter_local",
    "shimmer_local",
    "dup_flag",
    "order_flag",
    "f0_contour_hz",
]

# columns kept as text (everything else is coerced to float)
STRING_COLS = {
    "file",
    "token_id",
    "speaker",
    "rep_label",
    "segment_label",
    "sound_type",
    "status",
    "f0_contour_hz",
}

# landmark point -> its seconds column; drives the has_* availability flags
LANDMARK_COLS = {
    "t_clo": "t_clo_s",
    "t_burst": "t_burst_s",
    "t_voi": "t_voi_s",
    "t_vend": "t_vend_s",
    "t_glot_rel": "t_glot_rel_s",
    "t_pvend": "t_pvend_s",
}


class SchemaError(ValueError):
    pass


def parse_f0_contour(s):
    """';'-joined contour string -> float ndarray ('NA' -> nan). Empty -> empty array."""
    if s is None or pd.isna(s) or s in ("", "NA"):
        return np.array([], dtype=float)
    vals = []
    for tok in str(s).split(";"):
        tok = tok.strip()
        vals.append(np.nan if tok in ("", "NA") else float(tok))
    return np.array(vals, dtype=float)


def load_extraction(path):
    """Return a DataFrame for one speaker's extraction CSV.

    Adds: numeric coercion, `f0_contour` (ndarray), `has_<landmark>` booleans, `accepted`.
    Raises SchemaError if the header doesn't match EXTRACTION_COLUMNS exactly.
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)

    if list(df.columns) != EXTRACTION_COLUMNS:
        missing = [c for c in EXTRACTION_COLUMNS if c not in df.columns]
        extra = [c for c in df.columns if c not in EXTRACTION_COLUMNS]
        raise SchemaError(
            f"{path}: extraction header does not match the frozen schema.\n"
            f"  missing: {missing}\n  unexpected: {extra}\n"
            f"  (did 02_extract_measurements.praat change? update EXTRACTION_COLUMNS together.)"
        )

    for col in df.columns:
        if col in STRING_COLS:
            df[col] = df[col].where(df[col] != "NA", pd.NA)
        else:
            # to_numeric coerces the "NA" sentinel straight to NaN (no replace -> no downcast warning)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["f0_contour"] = df["f0_contour_hz"].apply(parse_f0_contour)
    for name, scol in LANDMARK_COLS.items():
        df[f"has_{name}"] = df[scol].notna()
    df["accepted"] = df["status"] == "accepted"

    return df


def status_counts(df):
    """Tally of the status column (accepted / skipped / garbage / partial / ...)."""
    return df["status"].value_counts(dropna=False).to_dict()
