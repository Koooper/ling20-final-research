"""The hand-check subset: a deterministic random sample of accepted tokens.

Serves three masters: the ~12% independent-remeasurement validation harness (template out,
filled values back in -> handcheck_compare), the FastTrack images mode (02b_formants.praat reads
handcheck_tokens_{speaker}.csv to render formant-winner comparison images only for these tokens,
rather than all ~300+), and determinism (same seed -> same sample).

Workflow: the pipeline writes handcheck_tokens_{speaker}.csv with blank HAND_COLS. The human
remeasures those tokens in Praat by hand and fills the blanks. Pointing the pipeline back at the
filled file runs handcheck_compare(): pipeline value vs hand value per measure, within the
per-measure tolerance from config.validation. This is the agreement check the paper's appendix
describes (no auto-placement; human owns the measurement layer).
"""

import numpy as np
import pandas as pd

# Blank columns the human fills in by hand. Each pairs with a pipeline column + a config tolerance.
HAND_COLS = ["hand_vot_ms", "hand_noise_cog_hz"]
COMPARE_SPEC = [
    # (pipeline_col, hand_col, tolerance_key, default_tolerance)
    ("vot_ms", "hand_vot_ms", "vot_tolerance_ms", 5.0),
    ("noise_cog_hz", "hand_noise_cog_hz", "cog_tolerance_hz", 200.0),
]


def _accepted(frame):
    if "accepted" in frame.columns:
        return frame[frame["accepted"].fillna(False).astype(bool)]
    return frame[frame["status"].eq("accepted")]


def handcheck_sample(frame, config):
    """Return a small DataFrame of sampled token_ids (+ context + blank HAND_COLS) for hand-checking.

    Fraction + seed come from config.validation (hand_check_fraction / hand_check_seed). The
    HAND_COLS are emitted blank for the human to fill; handcheck_compare reads them back.
    """
    v = config.validation
    frac = v.get("hand_check_fraction", 0.12)
    seed = v.get("hand_check_seed", 42)

    acc = _accepted(frame)
    cols = [c for c in ("token_id", "file", "speaker", "category", "place", "ft_ceiling_hz")
            if c in acc.columns]
    if len(acc) == 0:
        out = acc.loc[:, cols].reset_index(drop=True)
    else:
        n = max(1, round(len(acc) * frac))
        sample = acc.sample(n=n, random_state=seed)
        out = sample.loc[:, cols].sort_values("token_id").reset_index(drop=True)

    for c in HAND_COLS:
        out[c] = ""           # blank for the human; "" survives the keep_default_na=False reread
    return out


def handcheck_compare(frame, filled, config):
    """Compare pipeline measures against hand-remeasured values for the filled subset.

    `frame` is the pipeline (merged/derived) frame; `filled` is the hand-check CSV with HAND_COLS
    filled in. Returns a long DataFrame: one row per (token_id x measure) with pipeline value, hand
    value, abs diff, tolerance, and a verdict (within / OUT / no_hand_value / no_pipeline_value).
    """
    v = config.validation
    pipe = frame.set_index("token_id")
    rows = []
    for _, hrow in filled.iterrows():
        tid = hrow["token_id"]
        for pcol, hcol, tol_key, tol_def in COMPARE_SPEC:
            tol = float(v.get(tol_key, tol_def))
            hand = pd.to_numeric(pd.Series([hrow.get(hcol)]), errors="coerce").iloc[0]
            pval = (pd.to_numeric(pd.Series([pipe.at[tid, pcol]]), errors="coerce").iloc[0]
                    if tid in pipe.index and pcol in pipe.columns else np.nan)
            diff = abs(pval - hand) if (np.isfinite(pval) and np.isfinite(hand)) else np.nan
            if not np.isfinite(hand):
                verdict = "no_hand_value"
            elif not np.isfinite(pval):
                verdict = "no_pipeline_value"
            else:
                verdict = "within" if diff <= tol else "OUT"
            rows.append({
                "token_id": tid, "measure": pcol,
                "pipeline": round(float(pval), 3) if np.isfinite(pval) else np.nan,
                "hand": round(float(hand), 3) if np.isfinite(hand) else np.nan,
                "abs_diff": round(float(diff), 3) if np.isfinite(diff) else np.nan,
                "tolerance": tol, "verdict": verdict,
            })
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["token_id", "measure"]).reset_index(drop=True)
    return out
