"""Per-speaker analysis figures for the Lakota obstruents study.

Greenfield plotting layer. Draws from ONE speaker's derived token-grain frame (the
`merged_{sid}.csv` that run_pipeline writes - it is the post-derive frame, so silent_gap_ms,
gap_depth_db, f0_mid_hz and f0_onset_excursion_st are already columns). The two speakers are
NEVER pooled; every figure is one speaker's tokens. run_pipeline calls this per speaker; the
cross-speaker side-by-side views live in `compare.py` (descriptive only, stats stay separate).

Governing principle for n=2: never hide a token behind a bar + error bar. Every distribution
is a strip of individual points (seeded jitter, deterministic) with a box overlay and an
explicit per-cell n. A thin cell is supposed to look thin.

Figures (one function each; all robust to empty/missing cells, none ever raise):
  F1  fig_vot_ladder_q1     Q1  word-initial VOT by laryngeal x place - the centerpiece.
  F2  fig_vot_position_q1   Q1  VOT initial vs intervocalic, per laryngeal.
  F3  fig_guttural_cog_q2   Q2  aspiration-noise COG, glottal vs uvular (+ moment space).
  F5  fig_affricate_q3      Q3  the three cs: VOT strip + VOT x COG scatter.
  F6  fig_ejective_q4       Q4  canonicality dashboard - ejective vs non-ejective, 8 panels.
  F7  fig_inventory_vot     -   word-initial VOT across the whole inventory (descriptive shot).
  F8  fig_formant_method    -   FastTrack vs single-ceiling formant agreement (methods).

Run standalone (reads the already-written merged CSV, does NOT re-merge metadata):
    python python/figures.py --speaker S2
or let run_pipeline call make_figures() at its plotting seam.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: write PNGs, never open a window
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# ---------------------------------------------------------------------------
# shared vocabulary: orderings, IPA-ish labels, a colourblind-safe palette
# ---------------------------------------------------------------------------

# Okabe-Ito (colourblind-safe). Color means LARYNGEAL everywhere - one key, every figure.
LARYNGEAL_ORDER = ["plain", "aspirated_glottal", "aspirated_uvular", "ejective"]
LARYNGEAL_COLOR = {
    "plain": "#0072B2",            # blue
    "aspirated_glottal": "#E69F00",  # orange
    "aspirated_uvular": "#CC79A7",   # reddish purple (posterior -> deeper hue)
    "ejective": "#D55E00",         # vermillion (the strong one)
}
LARYNGEAL_LABEL = {
    "plain": "plain\nC",
    "aspirated_glottal": "glottal asp.\nCʰ",
    "aspirated_uvular": "uvular asp.\nCȟ",
    "ejective": "ejective\nCʼ",
}
# compact two-line tick labels for narrow faceted panels (F1)
LARYNGEAL_LABEL_SHORT = {
    "plain": "C\nplain",
    "aspirated_glottal": "Cʰ\nglottal",
    "aspirated_uvular": "Cȟ\nuvular",
    "ejective": "Cʼ\nejective",
}

TITLE_PAD = 20  # lift a subplot title clear of the per-cell n= row that sits at the axes top

MANNER_ORDER = ["stop", "affricate", "fricative"]
PLACE_ORDER = ["labial", "coronal", "velar", "alveolar", "postalveolar", "uvular"]
NEUTRAL = "#5A5A5A"  # non-ejective / reference gray

# IPA glyphs (notably ȟ, U+021F) must render with the caron ON the h, not the preceding
# consonant. DejaVu Sans (matplotlib's default) mis-positions it; Segoe UI places it correctly
# and carries a bold weight (titles need it). Fallback chain keeps figures sane off-Windows.
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Charis SIL", "Gentium Plus", "Arial", "DejaVu Sans"],
    "figure.dpi": 130,
    "savefig.dpi": 300,            # print-grade for document inclusion
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": "#E6E6E6",
    "grid.linewidth": 0.8,
    "legend.frameon": False,
    "figure.facecolor": "white",
})


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------

def _accepted(df):
    """Boolean mask of accepted tokens, robust to the CSV's 'True'/'False' strings."""
    if "accepted" in df.columns:
        s = df["accepted"]
        if s.dtype == bool:
            return s
        return s.astype(str).str.strip().str.lower().isin(["true", "1"])
    return df.get("status", pd.Series("", index=df.index)).eq("accepted")


def _num(df, col):
    """A row-aligned numeric Series for a measure column (NA-coerced; empty if absent)."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def _lighten(color, amount):
    """Blend `color` toward white by `amount` in [0,1] (1.0 = white)."""
    r, g, b = mcolors.to_rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


def _strip_box(ax, cats_vals, *, colors, labels=None, jitter=0.09, size=26,
               annotate_n=True, rng=None, widths=0.55, ylog=False):
    """The workhorse: one box + jittered point cloud per category, with an explicit n.

    `cats_vals` is an ordered list of (label_key, 1-D array of present values). Empty arrays
    draw nothing but still reserve their x slot and an 'n=0', so a missing cell is visible as
    absence rather than a silent gap in the axis.
    """
    rng = np.random.default_rng(0) if rng is None else rng
    n = len(cats_vals)
    for i, (key, vals) in enumerate(cats_vals):
        vals = np.asarray(vals, dtype=float)
        vals = vals[np.isfinite(vals)]
        c = colors[i] if isinstance(colors, (list, tuple)) else colors.get(key, NEUTRAL)
        if len(vals):
            ax.boxplot(
                [vals], positions=[i], widths=widths, patch_artist=True, showfliers=False,
                zorder=2,
                medianprops=dict(color=c, lw=2.2),
                boxprops=dict(facecolor=_lighten(c, 0.86), edgecolor=c, lw=1.3),
                whiskerprops=dict(color=c, lw=1.2), capprops=dict(color=c, lw=1.2),
            )
            jx = i + rng.uniform(-jitter, jitter, size=len(vals))
            ax.scatter(jx, vals, s=size, color=c, edgecolor="white", linewidth=0.5,
                       alpha=0.9, zorder=3)
        if annotate_n:
            ax.annotate(f"n={len(vals)}", (i, 1.0), xycoords=("data", "axes fraction"),
                        xytext=(0, 5), textcoords="offset points", ha="center",
                        va="bottom", fontsize=7.5, color="#777")
    ax.set_xticks(range(n))
    ax.set_xticklabels([(labels.get(k, k) if labels else k) for k, _ in cats_vals])
    ax.set_xlim(-0.6, n - 0.4)
    if ylog:
        ax.set_yscale("log")


def _values_by(df, group_col, value_col, order):
    """[(key, present-values-array), ...] in `order`, accepted rows only already applied."""
    out = []
    v = _num(df, value_col)
    for key in order:
        sel = df[group_col].astype(str).eq(key)
        out.append((key, v[sel].dropna().to_numpy()))
    return out


def _supertitle(fig, sid, title, subtitle=None):
    fig.suptitle(f"{title}", fontsize=13, fontweight="bold", y=0.995)
    tag = f"speaker {sid}" + (f"  ·  {subtitle}" if subtitle else "")
    fig.text(0.5, 0.965, tag, ha="center", va="top", fontsize=9, color="#666")


def _save(fig, outdir, name):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# F1 - Q1: word-initial VOT by laryngeal x place  (the centerpiece)
# ---------------------------------------------------------------------------

def fig_vot_ladder_q1(df, sid, outdir):
    """Word-initial VOT, faceted by place, x = laryngeal. The plain/aspirated/ejective ladder.

    Stops only, initial only. Ejectives are hatched + flagged: their VOT (t_burst->t_voi)
    SUBSUMES the silent glottal gap, so it is not on the same footing as an aspiration lag -
    F6 shows the gap itself.
    """
    d = df[_accepted(df) & df["manner"].eq("stop") & df["position"].eq("initial")]
    places = [p for p in PLACE_ORDER if (d["place"].astype(str).eq(p)).any()]
    if not places:
        return None

    fig, axes = plt.subplots(1, len(places), figsize=(3.5 * len(places), 4.8),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, place in zip(axes, places):
        dp = d[d["place"].astype(str).eq(place)]
        cats = _values_by(dp, "laryngeal", "vot_ms", LARYNGEAL_ORDER)
        _strip_box(ax, cats, colors=LARYNGEAL_COLOR, labels=LARYNGEAL_LABEL_SHORT)
        # flag the ejective slot (its "VOT" includes the silent gap)
        ej_i = LARYNGEAL_ORDER.index("ejective")
        ax.axvspan(ej_i - 0.5, ej_i + 0.5, color="#D55E00", alpha=0.05, zorder=0)
        ax.set_title(place, pad=TITLE_PAD)
        ax.tick_params(axis="x", labelsize=8.5)
    axes[0].set_ylabel("VOT (ms)")
    _supertitle(fig, sid, "Word-initial VOT by laryngeal category",
                "stops only · shaded = ejective (VOT includes the silent gap, cf. F6)")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, outdir, "q1_vot_ladder")


# ---------------------------------------------------------------------------
# F2 - Q1: VOT initial vs intervocalic, per laryngeal
# ---------------------------------------------------------------------------

def fig_vot_position_q1(df, sid, outdir):
    """Stops: how VOT shifts from word-initial to intervocalic, per laryngeal category."""
    d = df[_accepted(df) & df["manner"].eq("stop")]
    lars = [l for l in LARYNGEAL_ORDER if d["laryngeal"].astype(str).eq(l).any()]
    if not lars:
        return None
    positions = ["initial", "intervocalic"]
    pos_color = {"initial": None, "intervocalic": None}  # colour by laryngeal, shade by pos

    fig, axes = plt.subplots(1, len(lars), figsize=(2.7 * len(lars), 4.4),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, lar in zip(axes, lars):
        dl = d[d["laryngeal"].astype(str).eq(lar)]
        base = LARYNGEAL_COLOR.get(lar, NEUTRAL)
        cats = _values_by(dl, "position", "vot_ms", positions)
        cols = [base, _lighten(base, 0.45)]
        _strip_box(ax, cats, colors=cols, labels={"initial": "init.", "intervocalic": "interV"})
        ax.set_title(LARYNGEAL_LABEL.get(lar, lar).replace("\n", " "), fontsize=10, pad=TITLE_PAD)
    axes[0].set_ylabel("VOT (ms)")
    _supertitle(fig, sid, "VOT by word position", "Plosives | Darker = Word-initial")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, outdir, "q1_vot_position")


# ---------------------------------------------------------------------------
# F2b - Q1: VOT by stress (the "stressed position" lens) - skips if stress unfilled
# ---------------------------------------------------------------------------

def fig_vot_stress_q1(df, sid, outdir):
    """Word-initial stop VOT split by lexical stress, per laryngeal. Returns None (draws
    nothing) until the `stress` column carries >=2 distinct values - so it is inert while
    stress is held/unfilled and lights up the moment the metadata does."""
    if "stress" not in df.columns:
        return None
    d = df[_accepted(df) & df["manner"].eq("stop") & df["position"].eq("initial")]
    levels = [v for v in ["stressed", "unstressed"]
              if d["stress"].astype(str).str.strip().eq(v).any()]
    if len(levels) < 2:
        return None
    lars = [l for l in LARYNGEAL_ORDER if d["laryngeal"].astype(str).eq(l).any()]
    fig, axes = plt.subplots(1, len(lars), figsize=(2.7 * len(lars), 4.4),
                             sharey=True, squeeze=False)
    axes = axes[0]
    for ax, lar in zip(axes, lars):
        dl = d[d["laryngeal"].astype(str).eq(lar)]
        base = LARYNGEAL_COLOR.get(lar, NEUTRAL)
        cols = [base, _lighten(base, 0.5)]
        _strip_box(ax, _values_by(dl, "stress", "vot_ms", levels), colors=cols,
                   labels={"stressed": "stress", "unstressed": "unstr."})
        ax.set_title(LARYNGEAL_LABEL.get(lar, lar).replace("\n", " "), fontsize=10, pad=TITLE_PAD)
    axes[0].set_ylabel("VOT (ms)")
    _supertitle(fig, sid, "Word-initial VOT by stress", "Plosives | Darker = Stressed")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, outdir, "q1_vot_stress")


# ---------------------------------------------------------------------------
# F3 - Q2: guttural aspiration COG, glottal vs uvular  (+ moment space)
# ---------------------------------------------------------------------------

def fig_guttural_cog_q2(df, sid, outdir):
    """Aspiration-noise COG: uvular (Cȟ) sits far below glottal (Cʰ) = more posterior source.

    Left: COG by place, glottal vs uvular pairs. Right: COG x spectral SD, the noise-source
    cloud. NOTE: the velar-vs-back-vowel conditioning that Q2 actually asks about needs
    following_vowel filled in the metadata; until then this is the place/laryngeal view only.
    """
    d = df[_accepted(df) & df["laryngeal"].isin(["aspirated_glottal", "aspirated_uvular"])]
    if d.empty:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))

    # left: grouped by place, glottal vs uvular
    ax = axes[0]
    places = [p for p in PLACE_ORDER if d["place"].astype(str).eq(p).any()]
    rng = np.random.default_rng(0)
    width = 0.34
    for i, place in enumerate(places):
        for j, lar in enumerate(["aspirated_glottal", "aspirated_uvular"]):
            vals = _num(d[d["place"].astype(str).eq(place) & d["laryngeal"].eq(lar)],
                        "noise_cog_hz").dropna().to_numpy()
            if not len(vals):
                continue
            c = LARYNGEAL_COLOR[lar]
            x0 = i + (j - 0.5) * width
            ax.boxplot([vals], positions=[x0], widths=width * 0.9, patch_artist=True,
                       showfliers=False, zorder=2,
                       medianprops=dict(color=c, lw=2),
                       boxprops=dict(facecolor=_lighten(c, 0.86), edgecolor=c, lw=1.1),
                       whiskerprops=dict(color=c, lw=1), capprops=dict(color=c, lw=1))
            ax.scatter(x0 + rng.uniform(-0.06, 0.06, len(vals)), vals, s=22, color=c,
                       edgecolor="white", linewidth=0.4, alpha=0.9, zorder=3)
    ax.set_xticks(range(len(places)))
    ax.set_xticklabels(places)
    ax.set_xlim(-0.6, len(places) - 0.4)
    ax.set_ylabel("aspiration-noise COG (Hz)")
    ax.set_title("COG by place")
    handles = [plt.Line2D([0], [0], marker="s", ls="", color=LARYNGEAL_COLOR[l],
                          label={"aspirated_glottal": "glottal Cʰ",
                                 "aspirated_uvular": "uvular Cȟ"}[l])
               for l in ["aspirated_glottal", "aspirated_uvular"]]
    ax.legend(handles=handles, loc="upper right", fontsize=9)

    # right: moment space COG x SD
    ax = axes[1]
    for lar in ["aspirated_glottal", "aspirated_uvular"]:
        dl = d[d["laryngeal"].eq(lar)]
        ax.scatter(_num(dl, "noise_cog_hz"), _num(dl, "noise_sd_hz"), s=34,
                   color=LARYNGEAL_COLOR[lar], edgecolor="white", linewidth=0.5, alpha=0.85,
                   label={"aspirated_glottal": "glottal Cʰ", "aspirated_uvular": "uvular Cȟ"}[lar])
    ax.set_xlabel("noise COG (Hz)")
    ax.set_ylabel("noise SD (Hz)")
    ax.set_title("noise-source space")
    ax.legend(loc="upper right", fontsize=9)

    _supertitle(fig, sid, "Guttural Aspiration Localization",
                "Uvular vs Glottal")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _save(fig, outdir, "q2_guttural_cog")


# ---------------------------------------------------------------------------
# F5 - Q3: the three cs - plain / aspirated / ejective affricate
# ---------------------------------------------------------------------------

def fig_affricate_q3(df, sid, outdir):
    """Affricate differentiation: the ejective separates on VOT + gap; plain vs aspirated barely.

    Left: VOT strip by laryngeal. Right: VOT x frication-COG - shows the three overlap on
    spectrum and split (only the ejective) on time.
    """
    d = df[_accepted(df) & df["manner"].eq("affricate")]
    if d.empty:
        return None
    # aspirated affricate may be coded glottal OR uvular (uvular tʃȟ in this data) - detect it.
    asp = next((l for l in ("aspirated_glottal", "aspirated_uvular")
                if d["laryngeal"].astype(str).eq(l).any()), None)
    order = [l for l in ["plain", asp, "ejective"]
             if l and d["laryngeal"].astype(str).eq(l).any()]
    labels = {"plain": "tʃ\nplain", "ejective": "tʃʼ\nejective",
              "aspirated_glottal": "tʃʰ\naspirated", "aspirated_uvular": "tʃȟ\naspirated"}

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))
    _strip_box(axes[0], _values_by(d, "laryngeal", "vot_ms", order),
               colors=LARYNGEAL_COLOR, labels=labels)
    axes[0].set_ylabel("VOT (ms)")
    axes[0].set_title("VOT by laryngeal", pad=TITLE_PAD)

    ax = axes[1]
    for lar in order:
        dl = d[d["laryngeal"].eq(lar)]
        ax.scatter(_num(dl, "vot_ms"), _num(dl, "noise_cog_hz"), s=40,
                   color=LARYNGEAL_COLOR[lar], edgecolor="white", linewidth=0.5, alpha=0.85,
                   label=labels[lar].replace("\n", " "))
    ax.set_xlabel("VOT (ms)")
    ax.set_ylabel("frication COG (Hz)")
    ax.set_title("time vs spectrum")
    ax.legend(loc="upper right", fontsize=9)

    _supertitle(fig, sid, "Affricate Differentiation", "Plain / Aspirated / Ejective ⟨č⟩")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return _save(fig, outdir, "q3_affricate")


# ---------------------------------------------------------------------------
# F5b - Q2e: /C_e/ lexicalization - realized COG vs the DOCUMENTED guttural
# ---------------------------------------------------------------------------

def fig_lexicalization_q2e(df, sid, outdir):
    """For /C_e/ items: does the realized aspiration COG track what the source DOCUMENTS the
    guttural as (documented_asp), or does /e/-context aspiration float free (coarticulation)?

    x = documented place (glottal/uvular); y = realized noise COG; points colored by the
    token's own realized laryngeal. Skips cleanly if documented_asp is unfilled.
    """
    if "documented_asp" not in df.columns:
        return None
    da = df["documented_asp"].astype(str).str.strip()
    d = df[_accepted(df) & da.ne("") & da.str.lower().ne("nan")]
    if d.empty:
        return None
    order = [v for v in ["glottal", "uvular"] if d["documented_asp"].astype(str).eq(v).any()]
    order += sorted(set(d["documented_asp"].astype(str)) - set(order) - {""})
    fig, ax = plt.subplots(figsize=(1.7 * len(order) + 3, 4.6))
    rng = np.random.default_rng(0)
    for i, doc in enumerate(order):
        sub = d[d["documented_asp"].astype(str).eq(doc)]
        vals = _num(sub, "noise_cog_hz").dropna()
        if len(vals):
            ax.boxplot([vals.to_numpy()], positions=[i], widths=0.55, patch_artist=True,
                       showfliers=False, zorder=2,
                       medianprops=dict(color=NEUTRAL, lw=2),
                       boxprops=dict(facecolor=_lighten(NEUTRAL, 0.9), edgecolor=NEUTRAL, lw=1.2),
                       whiskerprops=dict(color=NEUTRAL, lw=1), capprops=dict(color=NEUTRAL, lw=1))
        # color each point by its REALIZED laryngeal, to see if realization matches the doc
        for lar in ["aspirated_glottal", "aspirated_uvular"]:
            lv = _num(sub[sub["laryngeal"].astype(str).eq(lar)], "noise_cog_hz").dropna().to_numpy()
            if len(lv):
                ax.scatter(i + rng.uniform(-0.12, 0.12, len(lv)), lv, s=34,
                           color=LARYNGEAL_COLOR[lar], edgecolor="white", linewidth=0.5,
                           alpha=0.9, zorder=3)
        ax.annotate(f"n={len(vals)}", (i, 1.0), xycoords=("data", "axes fraction"),
                    xytext=(0, 5), textcoords="offset points", ha="center", va="bottom",
                    fontsize=8, color="#777")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([f"documented\n{o}" for o in order])
    ax.set_xlim(-0.6, len(order) - 0.4)
    ax.set_ylabel("realized aspiration COG (Hz)")
    handles = [plt.Line2D([0], [0], marker="o", ls="", color=LARYNGEAL_COLOR[l],
                          label={"aspirated_glottal": "realized glottal",
                                 "aspirated_uvular": "realized uvular"}[l])
               for l in ["aspirated_glottal", "aspirated_uvular"]]
    ax.legend(handles=handles, loc="best", fontsize=9, title="point color")
    _supertitle(fig, sid, "Guttural Lexicalization in the /Ce/ Context",
                "Realized COG vs documented place | Is /e/-aspiration fixed or gradient?")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, outdir, "q2e_lexicalization")


# ---------------------------------------------------------------------------
# F6 - Q4: ejective canonicality dashboard
# ---------------------------------------------------------------------------

def fig_ejective_q4(df, sid, outdir):
    """Eight-panel canonicality read: is the ejective a true glottalic egressive?

    Panel 1 is the ejective's own silent-gap distribution (the temporal signature). Panels
    2-8 put ejective beside non-ejective on the cues that should separate them if the glottis
    is tense into the vowel (gap depth, f0 onset, f0 excursion, H1-H2, HNR, jitter, shimmer).
    Mirrors the 'overall' scope of the instructor-mandated t-tests (points colored by manner
    so the manner mix in each box is visible).
    """
    d = df[_accepted(df)]
    if d.empty:
        return None
    is_ej = d["laryngeal"].astype(str).eq("ejective")
    manner_marker = {"stop": "o", "affricate": "s", "fricative": "^"}

    panels = [
        ("silent_gap_ms", "silent gap (ms)", True),       # ejective-only
        ("gap_depth_db", "gap depth (dB)", False),
        ("f0_onset_hz", "f0 onset (Hz)", False),
        ("f0_onset_excursion_st", "f0 onset excursion (st)", False),
        ("h1_h2_db", "H1–H2 (dB)", False),
        ("hnr_db", "HNR (dB)", False),
        ("jitter_local", "jitter (local)", False),
        ("shimmer_local", "shimmer (local)", False),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(15, 8))
    rng = np.random.default_rng(0)
    for ax, (col, ylab, ej_only) in zip(axes.ravel(), panels):
        groups = [("ejective", d[is_ej], LARYNGEAL_COLOR["ejective"])]
        if not ej_only:
            groups.insert(0, ("non-ejective", d[~is_ej], NEUTRAL))
        for i, (key, g, c) in enumerate(groups):
            vals = _num(g, col)
            present = g[vals.notna()]
            pv = vals.dropna().to_numpy()
            if len(pv):
                ax.boxplot([pv], positions=[i], widths=0.55, patch_artist=True,
                           showfliers=False, zorder=2,
                           medianprops=dict(color=c, lw=2.2),
                           boxprops=dict(facecolor=_lighten(c, 0.86), edgecolor=c, lw=1.3),
                           whiskerprops=dict(color=c, lw=1.1), capprops=dict(color=c, lw=1.1))
                # points, shaped by manner
                for mn, mk in manner_marker.items():
                    sub = present[present["manner"].astype(str).eq(mn)]
                    sv = _num(sub, col).dropna().to_numpy()
                    if len(sv):
                        ax.scatter(i + rng.uniform(-0.1, 0.1, len(sv)), sv, s=22, marker=mk,
                                   color=c, edgecolor="white", linewidth=0.4, alpha=0.85, zorder=3)
            ax.annotate(f"n={len(pv)}", (i, 1.0), xycoords=("data", "axes fraction"),
                        xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                        fontsize=7.5, color="#777")
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels([k for k, _, _ in groups], fontsize=9)
        ax.set_xlim(-0.6, len(groups) - 0.4)
        ax.set_ylabel(ylab)

    # manner-shape legend on the first axis
    mh = [plt.Line2D([0], [0], marker=m, ls="", color="#999", label=mn)
          for mn, m in manner_marker.items()]
    axes.ravel()[0].legend(handles=mh, loc="upper left", fontsize=8, title="manner",
                           title_fontsize=8)
    _supertitle(fig, sid, "Ejective Canonicality",
                "Strong silent gap vs muted f0 / voice-quality cues into the vowel")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _save(fig, outdir, "q4_ejective_canonicality")


# ---------------------------------------------------------------------------
# F7 - word-initial VOT across the whole inventory (descriptive centerpiece)
# ---------------------------------------------------------------------------

def fig_inventory_vot(df, sid, outdir):
    """Every word-initial obstruent's VOT on one ladder, ordered manner -> laryngeal.

    Uses a manner+laryngeal composite so the aspirated stops split into glottal vs uvular
    (the category column lumps them). Ejective slots are flagged (VOT ⊇ silent gap). Horizontal
    so the long category names read straight.
    """
    d = df[_accepted(df) & df["position"].eq("initial")].copy()
    if d.empty:
        return None
    d["ml"] = d["manner"].astype(str) + "|" + d["laryngeal"].astype(str)

    rows = []  # (manner, laryngeal, key) in display order
    for mn in MANNER_ORDER:
        for lar in LARYNGEAL_ORDER:
            key = f"{mn}|{lar}"
            if d["ml"].eq(key).any():
                rows.append((mn, lar, key))
    if not rows:
        return None

    fig, ax = plt.subplots(figsize=(9, 0.55 * len(rows) + 1.8))
    rng = np.random.default_rng(0)
    yticklabels = []
    for i, (mn, lar, key) in enumerate(rows):
        vals = _num(d[d["ml"].eq(key)], "vot_ms").dropna().to_numpy()
        c = LARYNGEAL_COLOR.get(lar, NEUTRAL)
        if len(vals):
            ax.boxplot([vals], positions=[i], widths=0.55, vert=False, patch_artist=True,
                       showfliers=False, zorder=2,
                       medianprops=dict(color=c, lw=2.2),
                       boxprops=dict(facecolor=_lighten(c, 0.86), edgecolor=c, lw=1.3),
                       whiskerprops=dict(color=c, lw=1.1), capprops=dict(color=c, lw=1.1))
            ax.scatter(vals, i + rng.uniform(-0.12, 0.12, len(vals)), s=24, color=c,
                       edgecolor="white", linewidth=0.5, alpha=0.9, zorder=3)
        lar_short = {"plain": "plain", "aspirated_glottal": "aspⁿ glottal",
                     "aspirated_uvular": "aspⁿ uvular", "ejective": "ejective"}[lar]
        yticklabels.append(f"{mn} · {lar_short}  (n={len(vals)})")
        if lar == "ejective":
            ax.axhspan(i - 0.5, i + 0.5, color="#D55E00", alpha=0.05, zorder=0)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(yticklabels, fontsize=9)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.invert_yaxis()  # stops at top
    ax.set_xlabel("word-initial VOT (ms)")
    ax.grid(axis="y", visible=False)
    _supertitle(fig, sid, "Word-initial VOT across the inventory",
                "ordered manner → laryngeal · shaded = ejective (VOT includes the silent gap)")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save(fig, outdir, "inventory_vot")


# ---------------------------------------------------------------------------
# F8 - methods: FastTrack (canonical) vs single-ceiling formants
# ---------------------------------------------------------------------------

def fig_formant_method(df, sid, outdir):
    """Canonical (FastTrack) vs single-ceiling formants, onset slots, identity line.

    Defends the canonical-formant choice: shows how far the smoothness-winning ceiling moved
    each estimate off the fixed-ceiling one. Only tokens with both present are drawn.
    """
    d = df[_accepted(df)]
    slots = [("f1_onset_hz", "F1"), ("f2_onset_hz", "F2"), ("f3_onset_hz", "F3")]
    if not any((d[s].notna().any() if s in d.columns else False) for s, _ in slots):
        return None
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.3))
    for ax, (slot, name) in zip(axes, slots):
        can = _num(d, slot)
        sc = _num(d, "sc_" + slot)
        both = can.notna() & sc.notna()
        x, y = sc[both].to_numpy(), can[both].to_numpy()
        if len(x):
            lo = min(x.min(), y.min())
            hi = max(x.max(), y.max())
            ax.plot([lo, hi], [lo, hi], color="#BBBBBB", lw=1, ls="--", zorder=1)
            ax.scatter(x, y, s=26, color="#0072B2", edgecolor="white", linewidth=0.4,
                       alpha=0.8, zorder=2)
            mad = float(np.mean(np.abs(y - x)))
            ax.annotate(f"n={len(x)}\nmean |Δ|={mad:.0f} Hz", (0.04, 0.96),
                        xycoords="axes fraction", va="top", ha="left", fontsize=8.5,
                        color="#555")
        ax.set_xlabel(f"single-ceiling {name} (Hz)")
        ax.set_ylabel(f"FastTrack {name} (Hz)")
        ax.set_title(name)
    _supertitle(fig, sid, "Methods · FastTrack vs single-ceiling formants", "vowel-onset slots")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    return _save(fig, outdir, "formant_method")


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

ALL_FIGURES = [
    fig_vot_ladder_q1, fig_vot_position_q1, fig_vot_stress_q1, fig_guttural_cog_q2,
    fig_affricate_q3, fig_lexicalization_q2e, fig_ejective_q4, fig_inventory_vot,
    fig_formant_method,
]


def make_figures(df, sid, outdir):
    """Draw every figure for one speaker's derived frame. Robust: a single failing figure is
    reported and skipped, never killing the run. Returns the list of written paths.

    `df` is the post-derive token-grain frame (same object run_pipeline holds at its plotting
    seam, or the round-tripped merged_{sid}.csv). `outdir` is figures/{sid}.
    """
    written, failed = [], []
    for fn in ALL_FIGURES:
        try:
            path = fn(df, sid, outdir)
            if path is not None:
                written.append(path)
        except Exception as exc:  # noqa: BLE001 - a bad cell must not abort the pipeline
            failed.append((fn.__name__, repr(exc)))
    return {"written": written, "failed": failed}


def load_speaker_frame(sid, config=None):
    """Read the already-written merged_{sid}.csv (the derived frame). Does NOT re-merge
    metadata - safe to call while words_metadata.csv is being edited."""
    if config is None:
        import config_loader
        config = config_loader.load_config()
    merged_dir = config.repo_root / config.raw.get("paths", {}).get("merged",
                                                                    "data/derived/merged")
    path = merged_dir / f"merged_{sid}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"no merged frame for {sid}: {path} (run the pipeline first)")
    return pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)


def main(argv=None):
    import config_loader
    ap = argparse.ArgumentParser(description="Render per-speaker analysis figures.")
    ap.add_argument("--speaker", help="speaker id (default: every speaker in the config)")
    ap.add_argument("--config", help="path to pipeline_config.yaml")
    args = ap.parse_args(argv)

    config = config_loader.load_config(args.config)
    sids = [args.speaker] if args.speaker else config.speaker_ids()
    fig_root = config.repo_root / config.raw.get("paths", {}).get("figures", "figures")
    for sid in sids:
        try:
            frame = load_speaker_frame(sid, config)
        except FileNotFoundError as exc:
            print(f"  {sid}: {exc}")
            continue
        res = make_figures(frame, sid, fig_root / sid)
        print(f"\n=== {sid} ===  {len(res['written'])} figure(s) -> {fig_root / sid}")
        for p in res["written"]:
            print(f"  + {p.name}")
        for name, err in res["failed"]:
            print(f"  ! {name} FAILED: {err}")


if __name__ == "__main__":
    main()
