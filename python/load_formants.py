"""Load FastTrack formant measurements and join them onto the frame by token_id.

FastTrack (the vendored Praat plugin, run by praat/.../02b_formants.praat) is the CANONICAL
formant source: it sweeps many ceilings per vowel and picks the smoothest winner. Its values
own the plain column names (f1_onset_hz, f2_onset_hz, ...) that derive/analyze already read.
The single-ceiling formants from 02 ride alongside under sc_* names for the methods comparison.

This is the FIRST token-grain join in the pipeline - everything upstream is word-grain. The
contract: 02b builds token_id IDENTICALLY to 02 ({speaker}_{filestem}_{rep}_{segment}); if the
two drift, this join silently leaves canonical formants NaN (surfaced as a 'missing' coverage
verdict, not dropped).
"""

import pandas as pd

# the canonical formant columns FastTrack must supply (the names derive/analyze read)
CANONICAL_FORMANT_COLS = [
    "f1_onset_hz", "f2_onset_hz", "f3_onset_hz", "f1_mid_hz", "f2_mid_hz", "f3_mid_hz",
]
# diagnostics emitted per token for the validation flags
FT_DIAGNOSTIC_COLS = ["ft_ceiling_hz", "ft_minerror", "ft_ceiling_at_bound"]


def load_formants(path):
    """Read a formants_{speaker}.csv (token_id-keyed, utf-8-sig, ASCII).

    Permissive by design (unlike the frozen extraction schema): token_id stays a string,
    every other column is coerced to numeric (Praat 'NA' -> NaN). Trajectory (f*_p20/50/80)
    and DCT coefficient (f*_c0..) columns are carried through as-is if present.
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if "token_id" not in df.columns:
        raise ValueError(f"{path}: formants CSV has no token_id column")
    missing = [c for c in CANONICAL_FORMANT_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: formants CSV missing canonical column(s): {missing}")

    for col in df.columns:
        if col == "token_id":
            df[col] = df[col].where(df[col] != "NA", pd.NA)
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def merge_formants(frame, formants):
    """Left-join FastTrack formants onto `frame` by token_id. Returns (merged, report).

    Canonical formant + trajectory + coeff + ft_* columns land on the frame. A measurement
    token with no formant row keeps NaN canonical formants (coverage will read 'missing'); a
    formant row with no measurement token is reported as an orphan (likely token_id drift).
    """
    fcols = [c for c in formants.columns if c != "token_id"]
    dups = [c for c in fcols if c in frame.columns]
    if dups:
        # canonical names must not already exist on the frame (02 emits sc_* now)
        raise ValueError(f"formant columns already present on frame (schema drift?): {dups}")

    merged = frame.merge(
        formants, on="token_id", how="left", indicator="_ft"
    )

    measured = set(frame["token_id"])
    have_formant = set(formants["token_id"].dropna())
    formant_orphans = sorted(have_formant - measured)        # formant row, no measurement token
    no_formant = sorted(
        merged.loc[merged["_ft"] == "left_only", "token_id"].dropna().tolist()
    )  # measurement token, no formant row

    report = {
        "n_formant_rows": len(formants),
        "n_joined": int((merged["_ft"] == "both").sum()),
        "formant_orphans": formant_orphans,
        "tokens_without_formant": no_formant,
    }
    merged = merged.drop(columns=["_ft"])
    return merged, report
