"""Attach linguistic identity to the identity-blind extraction - the word-grain join.

The Praat filestem is lossy (00's sanitize() shreds non-ASCII), so we never parse the
word out of token_id. Instead, two hops:
    extraction.file  ==  words_manifest.filename     (the {NN}_{safeword} stem)
        -> recovers words_manifest.word_label (raw orthography)
    normalize_orthography(word_label)  ==  words_metadata.word_norm
        -> attaches target/category/place/position/...
Both sides pass through the SAME normalize_orthography(), or the join silently breaks.
"""

import pandas as pd

try:                                  # works both as a package module and flat on sys.path
    from python.orthography import normalize_orthography
except ImportError:                   # pragma: no cover
    from orthography import normalize_orthography

# identity columns pulled in from words_metadata (only those present are taken)
_META_COLS = [
    "word", "gloss", "target", "category", "manner", "place", "laryngeal",
    "position", "following_vowel", "stress", "documented_asp", "probe",
    "provenance", "preceding_seg", "notes",
]


def _read_csv_smart(path):
    """Read a CSV whatever its BOM says: UTF-16 (Praat) or UTF-8(-sig)."""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    elif head[:3] == b"\xef\xbb\xbf":
        enc = "utf-8-sig"
    else:
        enc = "utf-8"
    return pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)


def load_manifest(path):
    """words_manifest.csv (UTF-16, Praat-written). Adds normalized word_norm."""
    df = _read_csv_smart(path)
    df["word_norm"] = df["word_label"].map(normalize_orthography)
    return df


def load_words_metadata(path):
    """config/words_metadata.csv (utf-8-sig). Adds normalized word_norm (idempotent)."""
    df = _read_csv_smart(path)
    df["word_norm"] = df["word"].map(normalize_orthography)
    return df


def merge_metadata(extraction, manifest, words_meta):
    """Join extraction -> manifest -> words_metadata. Returns (merged_df, report dict)."""
    # stage 1: file stem -> manifest -> raw word label
    man = manifest[["filename", "word_label", "word_norm"]].drop_duplicates("filename")
    m1 = extraction.merge(
        man, left_on="file", right_on="filename", how="left", indicator="_man"
    )

    # stage 2: normalized word -> linguistic identity
    keep = ["word_norm"] + [c for c in _META_COLS if c in words_meta.columns]
    meta = words_meta[keep].drop_duplicates("word_norm")
    merged = m1.merge(meta, on="word_norm", how="left", indicator="_meta")

    # ---- reports (silent drops made visible) ----
    no_manifest = sorted(m1.loc[m1["_man"] == "left_only", "file"].dropna().unique().tolist())
    no_meta_tokens = merged.loc[
        (merged["_man"] == "both") & (merged["_meta"] == "left_only"), "token_id"
    ].tolist()
    matched_words = set(merged.loc[merged["_meta"] == "both", "word_norm"].dropna())
    unused_meta_words = sorted(set(words_meta["word_norm"].dropna()) - matched_words)

    report = {
        "n_rows": len(merged),
        "n_joined": int((merged["_meta"] == "both").sum()),
        "orphans_no_manifest": no_manifest,        # file stem not in the slice manifest
        "orphans_no_metadata": no_meta_tokens,     # word has no words_metadata row
        "unused_metadata_words": unused_meta_words,  # authored word never measured
    }

    merged = merged.drop(columns=["filename", "_man", "_meta"])
    return merged, report
