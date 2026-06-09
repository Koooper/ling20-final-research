"""Cross-speaker DESCRIPTIVE comparison layer for the Lakota obstruents study.

This is the second sanctioned place tokens sit beside each other across the speaker boundary
(the first being the instructor-mandated ejective t-tests in stats.py). The difference matters:
this layer emits NO p-values and makes NO inferential claim. With n=2 a p-value would be
pseudoreplicated theatre (Hurlbert 1984). Everything here answers one honest question -
"how similar do THESE two speakers look on this measure?" - and answers it with descriptive
effect sizes + distributional-overlap numbers, framed as description, never as inference.

Two deliverables, both keep the speakers visibly separate:
  * comparison TABLES  -> output/compare/compare_{view}.csv
      one row per (view-group x measure); per-speaker n/mean/sd side by side, the raw
      difference, and four similarity metrics (Cohen's d, overlap coeff, ratio-of-means+CV,
      word-level Pearson r). Reuses analyze.build_views() so the groupings are IDENTICAL to
      the per-speaker view tables - this is those tables zipped together, not a new analysis.
  * combined FIGURES   -> figures/compare/*.png
      speaker-DODGED twins of the per-speaker research figures: within each category cell S1
      and S2 sit side by side (S1 solid fill + circle markers, S2 hatched + triangles), so the
      between-speaker gap reads without the eye leaving the cell. Color still means LARYNGEAL
      (the per-speaker key); speaker is the secondary channel. Reuses figures.py's palette and
      low-level helpers. Divergence is meant to jump out.

Run standalone (reads the already-written merged_{sid}.csv frames):
    python python/compare.py
or let run_pipeline call run_compare() at its cross-speaker seam (next to the pooled t-tests).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import analyze as az  # noqa: E402  (build_views, _accepted, _has_values, _nonblank)
import figures as figs  # noqa: E402 (palette + _strip_box + low-level draw helpers)

try:
    from scipy.stats import norm  # noqa: E402
    try:                                   # SciPy >=1.12 renamed trapz -> trapezoid
        from scipy.integrate import trapezoid as _trapz
    except Exception:                      # pragma: no cover
        _trapz = np.trapz
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover - scipy is a declared dep, but degrade gracefully
    _HAVE_SCIPY = False

# Two speakers, fixed order. If the study ever scales past n=2 this whole module's framing
# (descriptive-only, no inference) is what flips - see the speaker-pool-expansion note.
S1, S2 = "S1", "S2"


# ---------------------------------------------------------------------------
# similarity metrics (all descriptive; none is a hypothesis test)
# ---------------------------------------------------------------------------

def _cohens_d(m1, s1, n1, m2, s2, n2):
    """Standardized mean difference (S1 - S2) on the pooled SD. Descriptive effect size:
    how far apart the two speakers sit in SD units. NaN if either cell is too thin to have
    a variance."""
    if any(pd.isna(x) for x in (m1, s1, n1, m2, s2, n2)) or n1 < 2 or n2 < 2:
        return np.nan
    num = (n1 - 1) * s1**2 + (n2 - 1) * s2**2
    denom = n1 + n2 - 2
    sp = np.sqrt(num / denom) if denom > 0 else np.nan
    if not sp or pd.isna(sp):
        return np.nan
    return round((m1 - m2) / sp, 3)


def _ovl(m1, s1, m2, s2):
    """Overlap coefficient of two Gaussians fit to the per-speaker (mean, sd): the area shared
    by both densities. 1.0 = indistinguishable, 0.0 = disjoint. The most intuitive 'how similar'
    number, but it ASSUMES each speaker's distribution is roughly normal - which for n~5 reps is
    a convenience, not a fact. Read it as a rough overlap index, not a probability."""
    if not _HAVE_SCIPY or any(pd.isna(x) for x in (m1, s1, m2, s2)):
        return np.nan
    if s1 <= 0 or s2 <= 0:
        return 1.0 if (s1 <= 0 and s2 <= 0 and m1 == m2) else np.nan
    lo = min(m1 - 5 * s1, m2 - 5 * s2)
    hi = max(m1 + 5 * s1, m2 + 5 * s2)
    xs = np.linspace(lo, hi, 4000)
    d1 = norm.pdf(xs, m1, s1)
    d2 = norm.pdf(xs, m2, s2)
    return round(float(_trapz(np.minimum(d1, d2), xs)), 3)


def _cv(mean, sd):
    """Coefficient of variation sd/|mean| - within-speaker spread, scale-free."""
    if pd.isna(mean) or pd.isna(sd) or mean == 0:
        return np.nan
    return round(sd / abs(mean), 3)


def _word_pearson(g1, g2, measure):
    """Pearson r between the two speakers' PER-WORD mean values for `measure`, aligned on the
    words both produced. Asks 'do the same lexical items pattern high/low for both speakers?' -
    agreement in SHAPE, orthogonal to agreement in level. Needs >=3 shared words to mean
    anything. Returns (r, n_shared_words)."""
    if "word" not in g1.columns or "word" not in g2.columns:
        return np.nan, 0

    def per_word(g):
        v = pd.to_numeric(g.get(measure), errors="coerce")
        return g.assign(_v=v).dropna(subset=["_v"]).groupby("word")["_v"].mean()

    a, b = per_word(g1), per_word(g2)
    shared = a.index.intersection(b.index)
    if len(shared) < 3:
        return np.nan, len(shared)
    av, bv = a.loc[shared].to_numpy(), b.loc[shared].to_numpy()
    if np.std(av) == 0 or np.std(bv) == 0:
        return np.nan, len(shared)
    return round(float(np.corrcoef(av, bv)[0, 1]), 3), len(shared)


# ---------------------------------------------------------------------------
# comparison table (per view) - same groupings as analyze, speakers zipped
# ---------------------------------------------------------------------------

COMPARE_COLS_TAIL = [
    "measure",
    "n_S1", "mean_S1", "sd_S1", "n_S2", "mean_S2", "sd_S2",
    "mean_diff", "cohens_d", "ovl", "ratio_means", "cv_S1", "cv_S2",
    "pearson_r_word", "n_words_shared", "note",
]


def _stats(vals):
    present = pd.to_numeric(vals, errors="coerce").dropna()
    n = len(present)
    return (
        n,
        round(float(present.mean()), 3) if n else np.nan,
        round(float(present.std(ddof=1)), 3) if n > 1 else np.nan,
    )


def compare_view(view, pooled):
    """One long-format comparison table for a view. Mirrors analyze.summarize_view's selection
    and group-degradation EXACTLY (same select mask, same _has_values drop of unfilled keys),
    then splits each (group x measure) cell by speaker and computes the similarity metrics."""
    mask = view.select(pooled).fillna(False).astype(bool) & az._accepted(pooled)
    sel = pooled[mask]

    gb = [c for c in view.group_by if c in sel.columns and az._has_values(sel[c])]
    if len(sel) == 0:
        return pd.DataFrame(columns=gb + COMPARE_COLS_TAIL), {"n_selected": 0, "group_by": gb}

    if gb:
        iterator = sel.groupby(gb, dropna=False, sort=True)
        groups = [(k if isinstance(k, tuple) else (k,), g) for k, g in iterator]
    else:
        groups = [(("_all_",), sel)]
        gb = ["group"]

    rows = []
    for keyvals, g in groups:
        g1 = g[g["speaker"].astype(str).eq(S1)]
        g2 = g[g["speaker"].astype(str).eq(S2)]
        for measure in view.measures:
            if measure not in g.columns:
                continue
            n1, m1, s1 = _stats(g1[measure])
            n2, m2, s2 = _stats(g2[measure])
            notes = []
            if n1 == 0 or n2 == 0:
                notes.append("measure absent for one speaker in this cell")
            if measure == "vot_ms" and any("ejective" in str(kv) for kv in keyvals):
                notes.append("ejective VOT includes the approximate glottal-release interval; "
                             "between-speaker difference may be partly measurement variance")
            note = "; ".join(notes)
            r, n_shared = _word_pearson(g1, g2, measure)
            row = {gb[i]: keyvals[i] for i in range(len(gb))}
            row.update({
                "measure": measure,
                "n_S1": n1, "mean_S1": m1, "sd_S1": s1,
                "n_S2": n2, "mean_S2": m2, "sd_S2": s2,
                "mean_diff": round(m1 - m2, 3) if not (pd.isna(m1) or pd.isna(m2)) else np.nan,
                "cohens_d": _cohens_d(m1, s1, n1, m2, s2, n2),
                "ovl": _ovl(m1, s1, m2, s2),
                "ratio_means": round(m1 / m2, 3) if not (pd.isna(m1) or pd.isna(m2) or m2 == 0) else np.nan,
                "cv_S1": _cv(m1, s1), "cv_S2": _cv(m2, s2),
                "pearson_r_word": r, "n_words_shared": n_shared,
                "note": note,
            })
            rows.append(row)

    table = pd.DataFrame(rows).sort_values(gb + ["measure"], na_position="last").reset_index(drop=True)
    return table, {"n_selected": int(len(sel)), "group_by": gb}


def write_compare_tables(pooled, outdir):
    """Write one compare_{view}.csv per view. Returns {view_name: path}."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = {}
    for view in az.build_views():
        table, _notes = compare_view(view, pooled)
        path = outdir / f"compare_{view.name}.csv"
        table.to_csv(path, index=False, encoding="utf-8-sig")
        written[view.name] = path
    return written


# ---------------------------------------------------------------------------
# combined figures - the two speakers DODGED within each category cell so they
# sit shoulder-to-shoulder (easier to compare than stacked facet rows). Colour
# still means LARYNGEAL (the per-speaker key); speaker is a SECONDARY channel:
#   S1 = solid fill + circle markers,  S2 = hatched fill + triangle markers.
# ---------------------------------------------------------------------------

from matplotlib.patches import Patch  # noqa: E402

SPK_ORDER = (S1, S2)
SPK_MARKER = {S1: "o", S2: "^"}
SPK_HATCH = {S1: "", S2: "////"}


def _frames_by_speaker(pooled):
    return {S1: pooled[pooled["speaker"].astype(str).eq(S1)],
            S2: pooled[pooled["speaker"].astype(str).eq(S2)]}


def _save(fig, outdir, name):
    return figs._save(fig, outdir, name)


def _color_for(colors, key, i):
    if isinstance(colors, dict):
        return colors.get(key, figs.NEUTRAL)
    if isinstance(colors, (list, tuple)):
        return colors[i]
    return colors


def _by_cat_speaker(by, frame_filter, group_col, value_col, cats):
    """{cat_key: {sid: present-values-array}} for a (filtered) frame, grouped by group_col."""
    out = {k: {} for k in cats}
    for sid in SPK_ORDER:
        d = frame_filter(by[sid])
        v = figs._num(d, value_col)
        for k in cats:
            sel = d[group_col].astype(str).eq(k)
            out[k][sid] = v[sel].dropna().to_numpy()
    return out


def _dodge_box(ax, cats, by_cat, *, colors, labels=None, vert=True, size=22,
               sub_frac=0.82, annotate_n=True, rng=None):
    """For each category in `cats`, draw one box + jittered point cloud PER SPEAKER, dodged
    within the category slot. `by_cat` is {cat_key: {sid: 1-D array}}. Colour comes from the
    category (so the laryngeal key still holds); speaker is hatch (box) + marker (points). An
    empty sub-cell still reserves its slot and prints n=0, so a missing speaker reads as a gap."""
    rng = np.random.default_rng(0) if rng is None else rng
    nspk = len(SPK_ORDER)
    subw = sub_frac / nspk
    for i, key in enumerate(cats):
        c = _color_for(colors, key, i)
        for j, sid in enumerate(SPK_ORDER):
            vals = np.asarray(by_cat.get(key, {}).get(sid, []), dtype=float)
            vals = vals[np.isfinite(vals)]
            pos = i + (j - (nspk - 1) / 2) * subw
            if len(vals):
                ax.boxplot(
                    [vals], positions=[pos], widths=subw * 0.9, vert=vert, patch_artist=True,
                    showfliers=False, zorder=2,
                    medianprops=dict(color=c, lw=2),
                    boxprops=dict(facecolor=figs._lighten(c, 0.86), edgecolor=c, lw=1.2,
                                  hatch=SPK_HATCH[sid]),
                    whiskerprops=dict(color=c, lw=1), capprops=dict(color=c, lw=1),
                )
                jit = rng.uniform(-subw * 0.35, subw * 0.35, size=len(vals))
                xs, ys = (pos + jit, vals) if vert else (vals, pos + jit)
                ax.scatter(xs, ys, s=size, color=c, edgecolor="white", linewidth=0.4,
                           alpha=0.9, marker=SPK_MARKER[sid], zorder=3)
            if annotate_n:
                if vert:
                    ax.annotate(f"{len(vals)}", (pos, 1.0), xycoords=("data", "axes fraction"),
                                xytext=(0, 3), textcoords="offset points", ha="center",
                                va="bottom", fontsize=6.5, color="#999")
                else:
                    ax.annotate(f"{len(vals)}", (1.0, pos), xycoords=("axes fraction", "data"),
                                xytext=(3, 0), textcoords="offset points", ha="left",
                                va="center", fontsize=6.5, color="#999")
    if vert:
        ax.set_xticks(range(len(cats)))
        ax.set_xticklabels([(labels.get(k, k) if labels else k) for k in cats])
        ax.set_xlim(-0.6, len(cats) - 0.4)
    else:
        ax.set_yticks(range(len(cats)))
        ax.set_yticklabels([(labels.get(k, k) if labels else k) for k in cats])
        ax.set_ylim(-0.6, len(cats) - 0.4)


def _speaker_legend(fig, loc="upper right"):
    """A small swatch legend mapping fill-hatch -> speaker (marker matches in the panels)."""
    handles = [Patch(facecolor="#DDDDDD", edgecolor="#555", hatch=SPK_HATCH[s], label=s)
               for s in SPK_ORDER]
    fig.legend(handles=handles, loc=loc, frameon=False, fontsize=9, title="speaker",
               title_fontsize=9)


# Ejective VOT carries a measurement caveat: it spans burst -> voicing and so subsumes the
# glottal-release interval, whose landmark (t_glot_rel) was placed approximately and sometimes
# sat near vowel onset. So a between-speaker ejective-VOT gap may be partly measurement variance,
# not a real production difference. Figures that show ejective VOT flag the slot with * and
# carry this footnote.
EJECTIVE_VOT_CAVEAT = (
    "* Ejective VOT spans burst→voicing and includes the glottal-release interval; "
    "glottal-release placement was approximate (occasionally near vowel onset), so "
    "between-speaker ejective-VOT differences may partly reflect measurement variance."
)


def _ejective_vot_footnote(fig):
    fig.text(0.5, 0.012, EJECTIVE_VOT_CAVEAT, ha="center", va="bottom", fontsize=7.5,
             color="#666", style="italic", wrap=True)


def cmp_vot_ladder_q1(by, outdir):
    """Q1 VOT ladder, speakers DODGED: cols = place, x = laryngeal, S1|S2 side by side per cell."""
    d_all = pd.concat(by.values(), ignore_index=True)
    d_all = d_all[figs._accepted(d_all) & d_all["manner"].eq("stop") & d_all["position"].eq("initial")]
    places = [p for p in figs.PLACE_ORDER if d_all["place"].astype(str).eq(p).any()]
    if not places:
        return None
    lars = figs.LARYNGEAL_ORDER

    def filt(d):
        return d[figs._accepted(d) & d["manner"].eq("stop") & d["position"].eq("initial")]

    labels = dict(figs.LARYNGEAL_LABEL_SHORT)
    labels["ejective"] = labels["ejective"].replace("Cʼ", "Cʼ *")  # flag the VOT caveat
    fig, axes = plt.subplots(1, len(places), figsize=(2.9 * len(places), 4.8),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, place in zip(axes, places):
        by_cat = _by_cat_speaker(by, lambda d, p=place: filt(d)[filt(d)["place"].astype(str).eq(p)],
                                 "laryngeal", "vot_ms", lars)
        _dodge_box(ax, lars, by_cat, colors=figs.LARYNGEAL_COLOR, labels=labels)
        ej_i = lars.index("ejective")
        ax.axvspan(ej_i - 0.5, ej_i + 0.5, color="#D55E00", alpha=0.05, zorder=0)
        ax.set_title(place.capitalize(), pad=figs.TITLE_PAD)
        ax.tick_params(axis="x", labelsize=8.5)
    axes[0].set_ylabel("VOT (ms)")
    fig.suptitle("Word-Initial VOT by Laryngeal Category", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.945, "Plosives | Shaded = ejective (VOT includes the silent gap) | S1 solid circles, S2 hatched triangles",
             ha="center", va="top", fontsize=9, color="#666")
    _speaker_legend(fig)
    _ejective_vot_footnote(fig)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return _save(fig, outdir, "compare_q1_vot_ladder")


def cmp_vot_position_q1(by, outdir):
    """Q1 VOT initial vs intervocalic, speakers dodged: cols = laryngeal, x = position."""
    d_all = pd.concat(by.values(), ignore_index=True)
    d_all = d_all[figs._accepted(d_all) & d_all["manner"].eq("stop")]
    lars = [l for l in figs.LARYNGEAL_ORDER if d_all["laryngeal"].astype(str).eq(l).any()]
    if not lars:
        return None
    positions = ["initial", "intervocalic"]

    def filt(d):
        return d[figs._accepted(d) & d["manner"].eq("stop")]

    fig, axes = plt.subplots(1, len(lars), figsize=(2.9 * len(lars), 4.8),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, lar in zip(axes, lars):
        by_cat = _by_cat_speaker(by, lambda d, l=lar: filt(d)[filt(d)["laryngeal"].astype(str).eq(l)],
                                 "position", "vot_ms", positions)
        _dodge_box(ax, positions, by_cat, colors=figs.LARYNGEAL_COLOR.get(lar, figs.NEUTRAL),
                   labels={"initial": "initial", "intervocalic": "intervoc."})
        title = figs.LARYNGEAL_LABEL.get(lar, lar).replace("\n", " ")
        if lar == "ejective":
            title += " *"
        ax.set_title(title, fontsize=10, pad=figs.TITLE_PAD)
    axes[0].set_ylabel("VOT (ms)")
    fig.suptitle("VOT by Word Position", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.945, "Plosives | S1 solid circles, S2 hatched triangles", ha="center", va="top",
             fontsize=9, color="#666")
    _speaker_legend(fig)
    _ejective_vot_footnote(fig)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return _save(fig, outdir, "compare_q1_vot_position")


def cmp_guttural_cog_q2(by, outdir):
    """Q2 aspiration-noise COG, glottal vs uvular, speakers dodged: cols = place, x = laryngeal."""
    lars = ["aspirated_glottal", "aspirated_uvular"]
    d_all = pd.concat(by.values(), ignore_index=True)
    d_all = d_all[figs._accepted(d_all) & d_all["laryngeal"].isin(lars)]
    places = [p for p in figs.PLACE_ORDER if d_all["place"].astype(str).eq(p).any()]
    if not places:
        return None

    def filt(d):
        return d[figs._accepted(d) & d["laryngeal"].isin(lars)]

    fig, axes = plt.subplots(1, len(places), figsize=(2.7 * len(places) + 1, 4.8),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, place in zip(axes, places):
        by_cat = _by_cat_speaker(by, lambda d, p=place: filt(d)[filt(d)["place"].astype(str).eq(p)],
                                 "laryngeal", "noise_cog_hz", lars)
        _dodge_box(ax, lars, by_cat, colors=figs.LARYNGEAL_COLOR,
                   labels={"aspirated_glottal": "Cʰ\nglottal", "aspirated_uvular": "Čh\nuvular"})
        ax.set_title(place.capitalize(), pad=figs.TITLE_PAD)
        ax.tick_params(axis="x", labelsize=8.5)
    axes[0].set_ylabel("aspiration-noise COG (Hz)")
    fig.suptitle("Guttural Aspiration Spectral COG: Glottal vs Uvular", fontsize=13,
                 fontweight="bold")
    fig.text(0.5, 0.945, "S1 solid circles, S2 hatched triangles",
             ha="center", va="top", fontsize=9, color="#666")
    _speaker_legend(fig)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, outdir, "compare_q2_guttural_cog")


def cmp_affricate_q3(by, outdir):
    """Q3 affricate VOT by laryngeal, speakers dodged on one axis: x = the three c's."""
    d_all = pd.concat(by.values(), ignore_index=True)
    d_all = d_all[figs._accepted(d_all) & d_all["manner"].eq("affricate")]
    asp = next((l for l in ("aspirated_glottal", "aspirated_uvular")
                if d_all["laryngeal"].astype(str).eq(l).any()), None)
    order = [l for l in ["plain", asp, "ejective"]
             if l and d_all["laryngeal"].astype(str).eq(l).any()]
    if not order:
        return None
    asp_ipa = "tʃȟ" if asp == "aspirated_uvular" else "tʃʰ"
    labels = {"plain": "tʃ\nplain", "ejective": "tʃʼ *\nejective",
              "aspirated_glottal": "tʃʰ\naspirated", "aspirated_uvular": "tʃȟ\naspirated"}

    def filt(d):
        return d[figs._accepted(d) & d["manner"].eq("affricate")]

    fig, ax = plt.subplots(figsize=(1.9 * len(order) + 2.5, 4.8))
    by_cat = _by_cat_speaker(by, filt, "laryngeal", "vot_ms", order)
    _dodge_box(ax, order, by_cat, colors=figs.LARYNGEAL_COLOR, labels=labels)
    ax.set_ylabel("VOT (ms)")
    fig.suptitle("Affricate VOT by Laryngeal Category", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.94, f"Plain tʃ / aspirated {asp_ipa} / ejective tʃʼ | S1 solid circles, S2 hatched triangles",
             ha="center", va="top", fontsize=9, color="#666")
    _speaker_legend(fig)
    _ejective_vot_footnote(fig)
    fig.tight_layout(rect=(0, 0.06, 1, 0.91))
    return _save(fig, outdir, "compare_q3_affricate")


def cmp_lexicalization_q2e(by, outdir):
    """Q2e /C_e/ realized COG by documented place, speakers dodged. Skips if documented_asp
    unfilled for both speakers."""
    d_all = pd.concat(by.values(), ignore_index=True)
    if "documented_asp" not in d_all.columns:
        return None
    sel_all = d_all[figs._accepted(d_all) & az._nonblank(d_all["documented_asp"])]
    if sel_all.empty:
        return None
    order = [v for v in ["glottal", "uvular"] if sel_all["documented_asp"].astype(str).eq(v).any()]
    order += sorted(set(sel_all["documented_asp"].astype(str)) - set(order) - {""})

    def filt(d):
        return d[figs._accepted(d) & az._nonblank(d["documented_asp"])]

    fig, ax = plt.subplots(figsize=(2.1 * len(order) + 2.5, 4.8))
    by_cat = _by_cat_speaker(by, filt, "documented_asp", "noise_cog_hz", order)
    _dodge_box(ax, order, by_cat, colors=[figs.NEUTRAL] * len(order),
               labels={o: f"documented\n{o}" for o in order})
    ax.set_ylabel("realized aspiration COG (Hz)")
    fig.suptitle("Realized Aspiration COG by Documented Place (/Ce/ Context)", fontsize=13,
                 fontweight="bold")
    fig.text(0.5, 0.94, "Is /e/-context aspiration lexically fixed or gradient? | S1 solid circles, S2 hatched triangles",
             ha="center", va="top", fontsize=9, color="#666")
    _speaker_legend(fig)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    return _save(fig, outdir, "compare_q2e_lexicalization")


def cmp_ejective_q4(by, outdir):
    """Q4 canonicality, speakers dodged: one row of 8 cue panels; each panel x = ej/non-ej,
    with S1|S2 dodged inside each group. Colour = ej (vermillion) vs non-ej (grey)."""
    panels = [
        ("silent_gap_ms", "Silent gap (ms)", True),
        ("gap_depth_db", "Gap depth (dB)", False),
        ("f0_onset_hz", "f0 onset (Hz)", False),
        ("f0_onset_excursion_st", "f0 excursion (st)", False),
        ("h1_h2_db", "H1–H2 (dB)", False),
        ("hnr_db", "HNR (dB)", False),
        ("jitter_local", "Jitter (local)", False),
        ("shimmer_local", "Shimmer (local)", False),
    ]
    grp_color = {"ejective": figs.LARYNGEAL_COLOR["ejective"], "non-ejective": figs.NEUTRAL}
    fig, axes = plt.subplots(1, len(panels), figsize=(2.0 * len(panels) + 1, 4.8), squeeze=False)
    axes = axes[0]
    for ax, (col, ylab, ej_only) in zip(axes, panels):
        cats = ["ejective"] if ej_only else ["non-ejective", "ejective"]
        by_cat = {k: {} for k in cats}
        for sid in SPK_ORDER:
            d = by[sid][figs._accepted(by[sid])]
            is_ej = d["laryngeal"].astype(str).eq("ejective")
            by_cat["ejective"][sid] = figs._num(d[is_ej], col).dropna().to_numpy()
            if not ej_only:
                by_cat["non-ejective"][sid] = figs._num(d[~is_ej], col).dropna().to_numpy()
        _dodge_box(ax, cats, by_cat, colors=grp_color,
                   labels={"ejective": "Cʼ", "non-ejective": "other"}, size=16)
        ax.set_title(ylab, pad=figs.TITLE_PAD, fontsize=9.5)
        ax.tick_params(axis="x", labelsize=8.5)
    fig.suptitle("Ejective Canonicality Cues", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.945, "Ejective vs non-ejective obstruents per cue | S1 solid circles, S2 hatched triangles",
             ha="center", va="top", fontsize=9, color="#666")
    _speaker_legend(fig, loc="lower right")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, outdir, "compare_q4_ejective")


def cmp_inventory_vot(by, outdir):
    """Word-initial VOT across the whole inventory on ONE horizontal axis: rows = manner x
    laryngeal, S1|S2 dodged within each row. The descriptive centerpiece, speakers shoulder
    to shoulder so each row's S1-vs-S2 gap reads directly."""
    d_all = pd.concat(by.values(), ignore_index=True)
    d_all = d_all[figs._accepted(d_all) & d_all["position"].eq("initial")].copy()
    if d_all.empty:
        return None
    d_all["ml"] = d_all["manner"].astype(str) + "|" + d_all["laryngeal"].astype(str)
    rows = []
    for mn in figs.MANNER_ORDER:
        for lar in figs.LARYNGEAL_ORDER:
            key = f"{mn}|{lar}"
            if d_all["ml"].eq(key).any():
                rows.append((mn, lar, key))
    if not rows:
        return None
    keys = [key for _, _, key in rows]
    colors = {key: figs.LARYNGEAL_COLOR.get(lar, figs.NEUTRAL) for _, lar, key in rows}

    def filt(d):
        dd = d[figs._accepted(d) & d["position"].eq("initial")].copy()
        dd["ml"] = dd["manner"].astype(str) + "|" + dd["laryngeal"].astype(str)
        return dd

    by_cat = _by_cat_speaker(by, filt, "ml", "vot_ms", keys)
    lar_short = {"plain": "plain", "aspirated_glottal": "glottal asp.",
                 "aspirated_uvular": "uvular asp.", "ejective": "ejective *"}
    labels = {key: f"{mn.capitalize()} · {lar_short[lar]}" for mn, lar, key in rows}

    fig, ax = plt.subplots(figsize=(9.5, 0.6 * len(rows) + 2))
    _dodge_box(ax, keys, by_cat, colors=colors, labels=labels, vert=False, size=22)
    for i, (mn, lar, key) in enumerate(rows):
        if lar == "ejective":
            ax.axhspan(i - 0.5, i + 0.5, color="#D55E00", alpha=0.05, zorder=0)
    ax.invert_yaxis()
    ax.set_xlabel("Word-initial VOT (ms)")
    ax.grid(axis="y", visible=False)
    fig.suptitle("Word-Initial VOT Across the Obstruent Inventory", fontsize=13,
                 fontweight="bold", y=0.995)
    fig.text(0.5, 0.965, "Ordered manner → laryngeal | Shaded = ejective | S1 solid circles (upper), S2 hatched triangles (lower)",
             ha="center", va="top", fontsize=9, color="#666")
    _speaker_legend(fig, loc="lower right")
    _ejective_vot_footnote(fig)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return _save(fig, outdir, "compare_inventory_vot")


ALL_COMPARE_FIGURES = [
    cmp_vot_ladder_q1, cmp_vot_position_q1, cmp_guttural_cog_q2, cmp_affricate_q3,
    cmp_lexicalization_q2e, cmp_ejective_q4, cmp_inventory_vot,
]


def make_compare_figures(pooled, outdir):
    """Draw every combined figure. Robust: a single failing figure is reported and skipped,
    never killing the run (mirrors figures.make_figures)."""
    by = _frames_by_speaker(pooled)
    written, failed = [], []
    for fn in ALL_COMPARE_FIGURES:
        try:
            path = fn(by, outdir)
            if path is not None:
                written.append(path)
        except Exception as exc:  # noqa: BLE001
            failed.append((fn.__name__, repr(exc)))
    return {"written": written, "failed": failed}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def _load_pooled(config, sids):
    merged_dir = config.repo_root / config.raw.get("paths", {}).get("merged",
                                                                    "data/derived/merged")
    frames = []
    for sid in sids:
        p = merged_dir / f"merged_{sid}.csv"
        if p.is_file():
            frames.append(pd.read_csv(p, encoding="utf-8-sig", keep_default_na=False))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def run_compare(config, sids):
    """Cross-speaker descriptive layer: write the comparison tables + combined figures.

    Called from run_pipeline.main() at the cross-speaker seam, beside the pooled t-tests.
    DESCRIPTIVE ONLY - no p-values, no inference (see module docstring). Returns a digest dict
    or None if there are not >=2 speakers' frames to compare."""
    if len(sids) < 2:
        return None
    pooled = _load_pooled(config, sids)
    if pooled is None or pooled.empty:
        return None

    out_root = config.repo_root / config.raw.get("paths", {}).get("output", "output")
    fig_root = config.repo_root / config.raw.get("paths", {}).get("figures", "figures")
    tables = write_compare_tables(pooled, out_root / "compare")
    figres = make_compare_figures(pooled, fig_root / "compare")
    return {
        "tables": {k: str(v) for k, v in tables.items()},
        "figures_written": len(figres["written"]),
        "figures_failed": figres["failed"],
        "fig_dir": str(fig_root / "compare"),
        "table_dir": str(out_root / "compare"),
    }


def main(argv=None):
    import config_loader
    ap = argparse.ArgumentParser(description="Cross-speaker descriptive comparison (no inference).")
    ap.add_argument("--config", help="path to pipeline_config.yaml")
    args = ap.parse_args(argv)
    config = config_loader.load_config(args.config)
    sids = config.speaker_ids()
    digest = run_compare(config, sids)
    if digest is None:
        print("compare: need >=2 speakers with merged frames; nothing to do.")
        return
    print(f"compare tables -> {digest['table_dir']}  ({len(digest['tables'])} views)")
    print(f"compare figures: {digest['figures_written']} written -> {digest['fig_dir']}")
    if digest["figures_failed"]:
        print(f"  FIGURE FAILURES: {digest['figures_failed']}")


if __name__ == "__main__":
    main()
