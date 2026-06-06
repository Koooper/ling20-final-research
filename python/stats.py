"""Ejective vs non-ejective t-tests (per the supervising instructor's directive).

SCOPE NOTE — read before trusting a p-value. The rest of this pipeline is descriptive and
per-speaker by design (n=2 speakers). These t-tests POOL tokens (plus a per-speaker breakdown),
which is PSEUDOREPLICATED: repetitions of the same word by the same speaker are not independent,
and the two speakers have different baselines, so the effective N is inflated and the p-values
are anticonservative. Treat them as a within-sample descriptive contrast ("is there a measurable
difference in THIS data?"), NOT as inference about Lakota or revitalization speakers generally.
This caveat belongs in the paper's Methods/Limitations. Welch (unequal-variance), two-tailed.

Output (long): one row per (scope x comparison x measure). scope = pooled | {speaker}.
comparison = overall (ejective vs every non-ejective obstruent) + per manner (stop/affricate/
fricative: ejective vs non-ejective within that manner, so VOT isn't compared across manners).
"""

import numpy as np
import pandas as pd
from scipy import stats as scistats

try:                                  # works as a package module or flat on sys.path
    from python.derive import ALL_MEASURES
except ImportError:                   # pragma: no cover
    from derive import ALL_MEASURES

MANNERS = ["stop", "affricate", "fricative"]


def _accepted(frame):
    # prefer status (survives a CSV round-trip; an 'accepted' bool reread as the string "False"
    # would be truthy and silently wrong when pooling from merged_*.csv)
    if "status" in frame.columns:
        return frame[frame["status"].eq("accepted")]
    return frame[frame["accepted"].fillna(False).astype(bool)]


def _round(x, n):
    return round(float(x), n) if (x is not None and np.isfinite(x)) else np.nan


def _two_group(ej_vals, other_vals):
    """Welch two-tailed t-test + descriptives for one ejective vs non-ejective cell."""
    a = np.asarray(pd.to_numeric(ej_vals, errors="coerce"), dtype=float)
    b = np.asarray(pd.to_numeric(other_vals, errors="coerce"), dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    na, nb = len(a), len(b)
    row = {
        "n_ejective": na, "mean_ejective": _round(a.mean(), 3) if na else np.nan,
        "sd_ejective": _round(a.std(ddof=1), 3) if na > 1 else np.nan,
        "n_other": nb, "mean_other": _round(b.mean(), 3) if nb else np.nan,
        "sd_other": _round(b.std(ddof=1), 3) if nb > 1 else np.nan,
        "mean_diff": np.nan, "cohens_d": np.nan, "t": np.nan, "df": np.nan,
        "p_two_tailed": np.nan, "note": "",
    }
    if na < 2 or nb < 2:
        row["note"] = "n<2 in a group"
        return row
    if a.std(ddof=1) == 0 and b.std(ddof=1) == 0:
        row["note"] = "no variance in either group"
        return row
    t, p = scistats.ttest_ind(a, b, equal_var=False)          # Welch
    sa2, sb2 = a.var(ddof=1), b.var(ddof=1)
    denom = (sa2 / na) ** 2 / (na - 1) + (sb2 / nb) ** 2 / (nb - 1)
    df = ((sa2 / na + sb2 / nb) ** 2 / denom) if denom > 0 else np.nan
    sp = np.sqrt(((na - 1) * sa2 + (nb - 1) * sb2) / (na + nb - 2))
    d = (a.mean() - b.mean()) / sp if sp > 0 else np.nan
    row.update(mean_diff=_round(a.mean() - b.mean(), 3), cohens_d=_round(d, 3),
               t=_round(t, 3), df=_round(df, 1), p_two_tailed=_round(p, 4))
    return row


def ejective_ttests(frame, scope):
    """All ejective-vs-non-ejective t-tests for one scope (a speaker id, or 'pooled').

    `frame` is a merged/derived frame; only accepted tokens are used. Returns a long DataFrame.
    """
    acc = _accepted(frame)
    if "laryngeal" not in acc.columns:
        return pd.DataFrame()

    comparisons = [("overall", acc)]
    if "manner" in acc.columns:
        comparisons += [(m, acc[acc["manner"].eq(m)]) for m in MANNERS]

    rows = []
    for comp_name, sub in comparisons:
        lar = sub["laryngeal"]
        ej = sub[lar.eq("ejective")]
        other = sub[lar.notna() & ~lar.eq("ejective")]
        for meas in ALL_MEASURES:
            if meas not in sub.columns:
                continue
            stats_row = _two_group(ej[meas], other[meas])
            rows.append({"scope": scope, "comparison": comp_name, "measure": meas, **stats_row})

    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["comparison", "measure"]).reset_index(drop=True)
    return out
