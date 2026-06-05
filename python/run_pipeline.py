"""Orchestrate the math layer per speaker: load -> merge -> validate -> derive -> analyze.

No plotting - figures wait until there is real data to draw (a clearly-marked seam below
shows where a plot step will hook in). The two speakers are processed independently and
NEVER pooled.

Real use (once extractions exist):
    python python/run_pipeline.py                 # every speaker in the config
    python python/run_pipeline.py --speaker S1    # just one
The fixture-driven end-to-end test calls run_speaker() with explicit path overrides instead,
so it never touches data/derived/.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pandas as pd           # noqa: E402

import analyze as az          # noqa: E402
import config_loader          # noqa: E402
import derive as dv           # noqa: E402
import handcheck as hc        # noqa: E402
import load_extraction as le  # noqa: E402
import load_formants as lf    # noqa: E402
import merge_metadata as mm   # noqa: E402
import validate as val        # noqa: E402

VIEW_NAMES = ["full_inventory", "q1_stops", "q2_guttural", "q3_affricate", "q4_ejective"]


def _rel(config, key, default):
    return config.raw.get("paths", {}).get(key, default)


def run_speaker(sid, config, *, extraction_path=None, manifest_path=None,
                words_meta_path=None, formants_path=None, out_root=None, lenient=False):
    """Run the full math chain for one speaker, write artifacts, return a digest dict.

    Paths default to the config (real run). Tests pass explicit fixture paths + an out_root
    temp dir so nothing lands in the repo's data/derived/.
    """
    extraction_path = Path(extraction_path) if extraction_path else config.extraction_path(sid)
    manifest_path = Path(manifest_path) if manifest_path else config.manifest_path(sid)
    words_meta_path = Path(words_meta_path) if words_meta_path else config.path("words_metadata")
    formants_path = Path(formants_path) if formants_path else (
        config.path("extraction") / f"formants_{sid}.csv"
    )
    root = Path(out_root) if out_root else config.repo_root

    # ---- the chain ----
    ext = le.load_extraction(extraction_path)
    man = mm.load_manifest(manifest_path)
    meta = mm.load_words_metadata(words_meta_path)
    merged, mreport = mm.merge_metadata(ext, man, meta)

    # FastTrack canonical formants join in by token_id (the only token-grain join). The pass
    # may not have run yet (no formants CSV) - then canonical formants are simply all-NaN and
    # coverage reports them 'missing', so the rest of the pipeline still runs.
    if formants_path.is_file():
        merged, freport = lf.merge_formants(merged, lf.load_formants(formants_path))
    else:
        for c in lf.CANONICAL_FORMANT_COLS:
            merged[c] = pd.NA
        freport = {"n_formant_rows": 0, "n_joined": 0, "formant_orphans": [],
                   "tokens_without_formant": merged["token_id"].tolist(), "absent": True}

    report = val.validate(merged, config, mreport, formant_report=freport,
                          raise_on_error=not lenient)
    derived, coverage = dv.derive(merged, config)
    summaries = az.analyze(derived, coverage, config)
    comparison = az.formant_method_comparison(merged)
    handcheck = hc.handcheck_sample(merged, config)
    # --- plotting seam: figures(summaries, derived, config, root) would go here ---

    # ---- artifacts ----
    val_dir = root / _rel(config, "validation", "data/derived/validation")
    merged_dir = root / _rel(config, "merged", "data/derived/merged")
    out_dir = root / _rel(config, "output", "output") / sid
    derived_root = merged_dir.parent                      # data/derived/
    for d in (val_dir, merged_dir, out_dir, derived_root):
        d.mkdir(parents=True, exist_ok=True)

    (val_dir / f"validation_{sid}.txt").write_text(report.text(), encoding="utf-8")
    handcheck.to_csv(val_dir / f"handcheck_tokens_{sid}.csv", index=False, encoding="utf-8-sig")
    # the f0_contour ndarray column doesn't belong in a CSV; the string form rides along.
    derived.drop(columns=["f0_contour"], errors="ignore").to_csv(
        merged_dir / f"merged_{sid}.csv", index=False, encoding="utf-8-sig"
    )
    coverage.to_csv(derived_root / f"coverage_{sid}.csv", index=False, encoding="utf-8-sig")
    for name, table in summaries.items():
        table.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(out_dir / "formant_method_comparison.csv", index=False, encoding="utf-8-sig")

    # ---- digest ----
    # 'missing' = applicable-but-absent. Count only ACCEPTED tokens here: a skipped/garbage
    # token legitimately has no FastTrack row, so it isn't a gap to chase (the full coverage
    # CSV still records every token). This is the actionable summary.
    acc_ids = set(merged.loc[merged["accepted"], "token_id"]) if "accepted" in merged.columns \
        else set(merged.loc[merged["status"] == "accepted", "token_id"])
    miss = coverage[(coverage["status"] == "missing") & (coverage["token_id"].isin(acc_ids))]
    missing_by_measure = miss.groupby("measure").size().sort_index().to_dict()
    return {
        "speaker": sid,
        "n_tokens": len(merged),
        "n_joined": mreport["n_joined"],
        "validation_ok": report.ok,
        "status_counts": le.status_counts(ext),
        "category_counts": report.info.get("category_counts", {}),
        "missing_by_measure": missing_by_measure,
        "formants_joined": freport["n_joined"],
        "formants_absent": freport.get("absent", False),
        "view_rows": {name: len(t) for name, t in summaries.items()},
        "out_dir": str(out_dir),
    }


def _print_digest(d):
    print(f"\n=== {d['speaker']} ===")
    print(f"  tokens: {d['n_tokens']} ({d['n_joined']} joined to metadata)")
    print(f"  validation: {'OK' if d['validation_ok'] else 'ERRORS'}")
    print(f"  status: {d['status_counts']}")
    if d["formants_absent"]:
        print("  FastTrack formants: NONE (run 02b_formants.praat) - canonical formants all NA")
    else:
        print(f"  FastTrack formants joined: {d['formants_joined']}")
    if d["missing_by_measure"]:
        print(f"  MISSING (applicable but unmeasured) by measure: {d['missing_by_measure']}")
    print(f"  view rows: {d['view_rows']}")
    print(f"  -> {d['out_dir']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the Lakota obstruents math pipeline.")
    ap.add_argument("--speaker", help="one speaker id (default: every speaker in the config)")
    ap.add_argument("--config", help="path to pipeline_config.yaml (default: repo config)")
    ap.add_argument("--lenient", action="store_true",
                    help="continue past hard validation errors instead of raising")
    args = ap.parse_args(argv)

    config = config_loader.load_config(args.config)
    sids = [args.speaker] if args.speaker else config.speaker_ids()
    for sid in sids:
        _print_digest(run_speaker(sid, config, lenient=args.lenient))


if __name__ == "__main__":
    main()
