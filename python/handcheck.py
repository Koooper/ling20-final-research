"""The hand-check subset: a deterministic random sample of accepted tokens.

Serves two masters: the ~12% independent-remeasurement validation harness, and the FastTrack
images mode (02b_formants.praat reads handcheck_tokens_{speaker}.csv to render formant-winner
comparison images only for these tokens, rather than all ~300+). Same seed -> same sample.
"""

import pandas as pd


def _accepted(frame):
    if "accepted" in frame.columns:
        return frame[frame["accepted"].fillna(False).astype(bool)]
    return frame[frame["status"].eq("accepted")]


def handcheck_sample(frame, config):
    """Return a small DataFrame of sampled token_ids (+ context cols) for hand-checking.

    Fraction + seed come from config.validation (hand_check_fraction / hand_check_seed).
    """
    v = config.validation
    frac = v.get("hand_check_fraction", 0.12)
    seed = v.get("hand_check_seed", 42)

    acc = _accepted(frame)
    cols = [c for c in ("token_id", "file", "speaker", "category", "place", "ft_ceiling_hz")
            if c in acc.columns]
    if len(acc) == 0:
        return acc.loc[:, cols].reset_index(drop=True)

    n = max(1, round(len(acc) * frac))
    sample = acc.sample(n=n, random_state=seed)
    return sample.loc[:, cols].sort_values("token_id").reset_index(drop=True)
