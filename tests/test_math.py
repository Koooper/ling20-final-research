"""Math-layer test: derive -> analyze -> run_pipeline, on the synthetic S0 fixture.

No real recordings needed. Run with the project venv:
    python tests/test_math.py
Exits 0 on success, 1 on the first failed assertion (with a traceback). Verifies the derived
measures, the NA-with-reason coverage ledger, the property-dispatch views, and a full
end-to-end pipeline run into a temp dir (so nothing lands in data/derived/).
"""

import math
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "python"))

import pandas as pd  # noqa: E402

import analyze as az          # noqa: E402
import config_loader          # noqa: E402
import derive as dv           # noqa: E402
import load_extraction as le  # noqa: E402
import load_formants as lf    # noqa: E402
import merge_metadata as mm   # noqa: E402
import run_pipeline as rp      # noqa: E402

FIX = HERE / "fixtures"


def _merged():
    ext = le.load_extraction(FIX / "measurements_S0.csv")
    man = mm.load_manifest(FIX / "words_manifest.csv")
    meta = mm.load_words_metadata(FIX / "words_metadata.csv")
    merged, _ = mm.merge_metadata(ext, man, meta)
    merged, _ = lf.merge_formants(merged, lf.load_formants(FIX / "formants_S0.csv"))
    return merged


def test_derive_columns():
    derived, _ = dv.derive(_merged())
    d = derived.set_index("token_id")

    # f0_mid = median of the central third; for a 3-sample contour that's the middle sample.
    ej = d.loc["S0_03_tA_r1_s1"]           # contour 135;132;130
    assert ej["f0_mid_hz"] == 132.0
    # raised onset: 12*log2(135/132) ~ +0.389 st (positive = onset above the vowel body)
    assert math.isclose(ej["f0_onset_excursion_st"], 12 * math.log2(135 / 132), rel_tol=1e-6)
    assert ej["f0_onset_excursion_st"] > 0
    # silent_gap = -glottal_oral_ms = t_glot_rel - t_burst = +30 ms for the ejective
    assert ej["silent_gap_ms"] == 30.0
    assert d.loc["S0_09_cA_r1_s1"]["silent_gap_ms"] == 35.0

    # a plain stop is not an ejective -> no silent gap
    assert pd.isna(d.loc["S0_01_ta_r1_s1"]["silent_gap_ms"])
    return derived


def test_coverage_reasons(derived):
    _, coverage = dv.derive(_merged())
    cov = coverage.set_index(["token_id", "measure"])

    def verdict(tid, measure):
        return cov.loc[(tid, measure), "status"], cov.loc[(tid, measure), "reason"]

    # word-initial plain stop: closure does not apply -> n/a with the right reason
    s, r = verdict("S0_01_ta_r1_s1", "closure_dur_ms")
    assert s == "n/a" and "word-initial" in r

    # intervocalic stop with t_clo marked: closure measured -> present
    s, _ = verdict("S0_02_ata_r1_s1", "closure_dur_ms")
    assert s == "present"

    # intervocalic aspirated stop, but t_clo was NOT marked: closure APPLIES yet is NaN
    # -> 'missing' (the actionable bucket), not silently dropped
    s, r = verdict("S0_10_ate_r1_s1", "closure_dur_ms")
    assert s == "missing" and "t_clo not marked" in r

    # fricative never has a closure phase
    s, r = verdict("S0_04_sa_r1_s1", "closure_dur_ms")
    assert s == "n/a" and "fricative" in r

    # non-ejective -> silent_gap n/a; ejective -> present
    assert verdict("S0_01_ta_r1_s1", "silent_gap_ms")[0] == "n/a"
    assert verdict("S0_03_tA_r1_s1", "silent_gap_ms")[0] == "present"

    # ate has no FastTrack formant row -> canonical formant is 'missing' with that reason
    s, r = verdict("S0_10_ate_r1_s1", "f1_onset_hz")
    assert s == "missing" and "no FastTrack formant row" in r

    # every coverage row is classified and every non-present row carries a reason
    assert set(coverage["status"].unique()) <= {"present", "n/a", "missing"}
    non_present = coverage[coverage["status"] != "present"]
    assert (non_present["reason"].str.len() > 0).all()


def test_views():
    derived, coverage = dv.derive(_merged())
    views = az.analyze(derived, coverage)

    # q4 selects ONLY ejectives, across both manners (stop + affricate)
    q4 = views["q4_ejective"]
    assert set(q4["manner"].unique()) == {"stop", "affricate"}
    # silent_gap present once per ejective cell
    sg = q4[q4["measure"] == "silent_gap_ms"]
    assert (sg["n_present"] == 1).all() and len(sg) == 2

    # q1 is stops only: affricate/fricative places never leak in
    q1 = views["q1_stops"]
    assert "postalveolar" not in set(q1["place"].dropna())   # postalveolar = affricate place
    assert "uvular" not in set(q1["place"].dropna())

    # degrade-to-ungrouped: following_vowel is entirely unfilled -> dropped from q2 grouping
    q2 = views["q2_guttural"]
    assert "following_vowel" not in q2.columns
    assert "place" in q2.columns
    assert len(q2) > 0                                       # selection is non-empty

    # na_reasons surfaces WHY a cell is thin: both a 'missing' gap and a by-design 'n/a'
    q1_closure = q1[q1["measure"] == "closure_dur_ms"]
    blob = " ".join(q1_closure["na_reasons"])
    assert "t_clo not marked" in blob          # the intervocalic ate gap
    assert "word-initial" in blob              # the initial stops, by design


def test_formant_layer():
    merged = _merged()
    d = merged.set_index("token_id")
    # canonical (FastTrack) and single-ceiling (sc_) coexist and differ
    assert d.loc["S0_01_ta_r1_s1", "f1_onset_hz"] == 610
    assert d.loc["S0_01_ta_r1_s1", "sc_f1_onset_hz"] == 600
    # trajectory + DCT coeffs + diagnostics rode along
    for c in ("f1_p50_hz", "f1_c0", "ft_ceiling_hz", "ft_ceiling_at_bound"):
        assert c in merged.columns
    # methods comparison: 6 slots, some real divergence
    comp = az.formant_method_comparison(merged)
    assert len(comp) == 6
    assert (comp["mean_abs_diff_hz"].fillna(0) > 0).any()

    # orphan detection: a formant row whose token_id matches no measurement token is reported
    base, _ = mm.merge_metadata(
        le.load_extraction(FIX / "measurements_S0.csv"),
        mm.load_manifest(FIX / "words_manifest.csv"),
        mm.load_words_metadata(FIX / "words_metadata.csv"),
    )
    fm = lf.load_formants(FIX / "formants_S0.csv").copy()
    fm.loc[len(fm), "token_id"] = "S0_99_nonexistent_r1_s1"
    _, rpt = lf.merge_formants(base, fm)
    assert "S0_99_nonexistent_r1_s1" in rpt["formant_orphans"]


def test_pipeline_end_to_end():
    cfg = config_loader.load_config()
    with tempfile.TemporaryDirectory() as tmp:
        kw = dict(
            extraction_path=FIX / "measurements_S0.csv",
            manifest_path=FIX / "words_manifest.csv",
            words_meta_path=FIX / "words_metadata.csv",
            formants_path=FIX / "formants_S0.csv",
            out_root=tmp,
        )
        digest = rp.run_speaker("S0", cfg, **kw)
        root = Path(tmp)
        # artifacts exist
        assert (root / "data/derived/merged/merged_S0.csv").is_file()
        assert (root / "data/derived/coverage_S0.csv").is_file()
        assert (root / "data/derived/validation/validation_S0.txt").is_file()
        assert (root / "data/derived/validation/handcheck_tokens_S0.csv").is_file()
        assert (root / "output/S0/formant_method_comparison.csv").is_file()
        for name in rp.VIEW_NAMES:
            assert (root / "output" / "S0" / f"{name}.csv").is_file()

        assert digest["validation_ok"]
        assert not digest["formants_absent"] and digest["formants_joined"] >= 1
        # the deliberately-unmarked t_clo shows up as a real gap in the digest
        assert digest["missing_by_measure"].get("closure_dur_ms", 0) >= 1

        # merged carries BOTH canonical and single-ceiling formants
        import pandas as pd
        mrg = pd.read_csv(root / "data/derived/merged/merged_S0.csv", encoding="utf-8-sig")
        assert "f1_onset_hz" in mrg.columns and "sc_f1_onset_hz" in mrg.columns

        # determinism: a second run yields byte-identical view tables
        before = (root / "output/S0/q4_ejective.csv").read_bytes()
        rp.run_speaker("S0", cfg, **kw)
        assert (root / "output/S0/q4_ejective.csv").read_bytes() == before


def main():
    derived = test_derive_columns()
    test_coverage_reasons(derived)
    test_views()
    test_formant_layer()
    test_pipeline_end_to_end()
    print("ALL MATH-LAYER TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
