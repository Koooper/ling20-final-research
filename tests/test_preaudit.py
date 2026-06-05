"""Pre-audit chain test: config -> load -> merge -> validate, on a synthetic fixture.

No real recordings needed. Run with the project venv:
    python tests/test_preaudit.py
Exits 0 on success, 1 on the first failed assertion (with a traceback).
"""

import sys
import tempfile
import traceback
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "python"))

import pandas as pd  # noqa: E402

import config_loader  # noqa: E402
import load_extraction as le  # noqa: E402
import load_formants as lf  # noqa: E402
import merge_metadata as mm  # noqa: E402
import validate as val  # noqa: E402
from orthography import normalize_orthography  # noqa: E402

FIX = HERE / "fixtures"


def test_normalization_contract():
    # apostrophe variant (saltillo vs straight) collapses
    assert normalize_orthography("t’á") == normalize_orthography("t'á")
    # NFD (combining diacritic) composes to NFC
    assert normalize_orthography(unicodedata.normalize("NFD", "atá")) == "atá"
    # script-g lookalike folds to one canonical ǧ
    assert normalize_orthography("t'áɡ̌a") == normalize_orthography("t'áǧa")


def test_load_extraction():
    df = le.load_extraction(FIX / "measurements_S0.csv")
    # schema columns preserved, in order, before the derived ones
    assert list(df.columns)[: len(le.EXTRACTION_COLUMNS)] == le.EXTRACTION_COLUMNS
    assert len(df) == 14
    assert int(df["accepted"].sum()) == 13  # one skipped row excluded

    ta = df.set_index("token_id").loc["S0_01_ta_r1_s1"]
    assert ta["has_t_burst"] and not ta["has_t_clo"]      # word-initial: no closure
    assert pd.isna(ta["closure_dur_ms"])                  # NA parsed, not "NA" string
    assert list(ta["f0_contour"]) == [120.0, 121.0, 119.0]

    ata = df.set_index("token_id").loc["S0_02_ata_r1_s1"]
    assert ata["has_t_clo"]                               # intervocalic: closure present
    ej = df.set_index("token_id").loc["S0_03_tA_r1_s1"]
    assert ej["has_t_glot_rel"]                           # ejective: glottal release
    return df


def test_schema_contract_fails_loud():
    raw = (FIX / "measurements_S0.csv").read_text(encoding="utf-8-sig").splitlines()
    raw[0] = raw[0].replace("vot_ms", "VOT_MS")          # corrupt one header name
    tmp = Path(tempfile.gettempdir()) / "bad_measurements_S0.csv"
    tmp.write_text("\n".join(raw), encoding="utf-8-sig")
    try:
        le.load_extraction(tmp)
    except le.SchemaError:
        return
    raise AssertionError("expected SchemaError on a drifted header")


def test_merge(df):
    man = mm.load_manifest(FIX / "words_manifest.csv")
    meta = mm.load_words_metadata(FIX / "words_metadata.csv")
    merged, report = mm.merge_metadata(df, man, meta)

    assert report["orphans_no_manifest"] == []
    assert "S0_99_ghost_r1_s1" in report["orphans_no_metadata"]   # word not authored
    assert "kage" in report["unused_metadata_words"]              # authored, never measured
    assert report["n_joined"] == 13

    # the apostrophe-variant join (manifest ’  vs  metadata ') resolved via normalize
    ej = merged.set_index("token_id").loc["S0_03_tA_r1_s1"]
    assert ej["category"] == "stop_ejective"
    assert ej["place"] == "coronal"
    # orphan carries no identity
    ghost = merged.set_index("token_id").loc["S0_99_ghost_r1_s1"]
    assert pd.isna(ghost["category"])

    # FastTrack canonical formants join in by token_id (the only token-grain join)
    fm = lf.load_formants(FIX / "formants_S0.csv")
    merged, freport = lf.merge_formants(merged, fm)
    # canonical f*_onset come from FastTrack; sc_* are the single-ceiling co-compat from 02
    ta = merged.set_index("token_id").loc["S0_01_ta_r1_s1"]
    assert ta["f1_onset_hz"] == 610 and ta["sc_f1_onset_hz"] == 600
    assert "S0_10_ate_r1_s1" in freport["tokens_without_formant"]   # absent from formants CSV
    return merged, report, freport


def test_validate(merged, report, freport, cfg):
    # clean fixture: warnings allowed, no HARD errors -> no raise
    rep = val.validate(merged, cfg, report, freport)
    assert rep.ok
    assert any("kage" in w for w in rep.warnings)
    assert any("ghost" in w for w in rep.warnings)
    # FastTrack diagnostics surface as warnings: ceiling-at-boundary + the absent formant token
    assert any("ceiling hit the range edge" in w for w in rep.warnings)
    assert any("no FastTrack formant row" in w for w in rep.warnings)

    # HARD: duplicate token_id raises
    dupd = pd.concat([merged, merged.iloc[[0]]], ignore_index=True)
    try:
        val.validate(dupd, cfg, report, freport)
        raise AssertionError("expected ValidationError on duplicate token_id")
    except val.ValidationError:
        pass

    # HARD: a file stem with no manifest row raises
    try:
        val.validate(merged, cfg, {"orphans_no_manifest": ["weird_stem"]})
        raise AssertionError("expected ValidationError on manifest orphan")
    except val.ValidationError:
        pass

    # SOFT: scrambled formants surface as a warning (not a raise)
    bad = merged.copy()
    bad.loc[bad["token_id"] == "S0_01_ta_r1_s1", "f1_onset_hz"] = 2000.0  # F1 > F2
    rep2 = val.validate(bad, cfg, report, freport, raise_on_error=False)
    assert any("not ordered" in w for w in rep2.warnings)


def main():
    cfg = config_loader.load_config()
    test_normalization_contract()
    df = test_load_extraction()
    test_schema_contract_fails_loud()
    merged, report, freport = test_merge(df)
    test_validate(merged, report, freport, cfg)
    print("ALL PRE-AUDIT TESTS PASSED")
    print(f"  joined {report['n_joined']}/{report['n_rows']} tokens; "
          f"status counts: {le.status_counts(df)}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
