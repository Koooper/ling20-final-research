#!/usr/bin/env python3
"""
normalize_wordlist.py — turn the hand-kept Lakota word sheet into a machine-friendly
words_metadata.csv.

Two jobs:
  1. MELT the sound x position layout into one row per (sound, word, position).
  2. NORMALIZE the orthography so word strings join cleanly later — unify apostrophe
     variants, fold the script-g lookalike, then NFC. This is the headline:
     `normalize_orthography()` is a standalone, importable function.

Input layout (the human sheet, e.g. lakotafinaldatasetwordlist.csv):
    col0 = sound label, present only on the FIRST of each 2-row pair (forward-filled).
           may carry IPA: "tʃh <čh>"  (orthography in <>), "ȟ [χ]" (IPA in []).
    col1 = word-INITIAL example      "orthography (gloss)"
    col2 = word-INTERVOCALIC example  "orthography (gloss)"
    a fully blank ",," row separates sound families and is skipped.
Each 2-row pair therefore yields 4 word-rows: 2 initial + 2 intervocalic.

Output: words_metadata.csv (utf-8-sig, Excel-safe per the project encoding rules).

────────────────────────────────────────────────────────────────────────────────
JOIN-CORRECTNESS CONTRACT (read this):
  The canonical apostrophe char chosen here (U+0027) is INTERNAL. What matters for
  the eventual token_id/word join is that BOTH sides — this wordlist AND the Praat
  TextGrid word-tier labels — pass through `normalize_orthography()` before being
  compared. Run the TextGrid labels through this same function at merge time.
────────────────────────────────────────────────────────────────────────────────

This script makes exactly ONE set of linguistic claims: SOUND_TABLE below
(manner / place / laryngeal per sound). VERIFY IT. Everything else is mechanical.

stdlib only. Usage:
    python normalize_wordlist.py INPUT.csv -o config/words_metadata.csv [--report]
"""

import argparse
import csv
import sys
from pathlib import Path

# normalize_orthography is shared with the analysis pipeline (merge_metadata) so BOTH
# sides of the word join canonicalize identically - see python/orthography.py.
try:                                  # run as a script (python/ on sys.path) ...
    from orthography import normalize_orthography, nfc
except ImportError:                   # ... or imported as a package module
    from python.orthography import normalize_orthography, nfc


# ── the one linguistic claim: VERIFY THIS ───────────────────────────────────
# sound (normalized orthography) -> (manner, place, laryngeal)
# laryngeal ∈ {plain, aspirated_glottal, aspirated_uvular, ejective}
#   - aspirated_glottal  = orthographic Ch  (⟨tʰ⟩): glottal aspiration
#   - aspirated_uvular   = orthographic Cȟ  (⟨tȟ⟩): velar/uvular aspiration  ← Q2
# Praat's sound_type menu collapses both aspirations to "aspirated"; the
# glottal-vs-uvular contrast lives ONLY in `laryngeal`/`target` here.
_SOUND_TABLE_RAW = {
    # plain stops
    "p":  ("stop", "labial",  "plain"),
    "t":  ("stop", "coronal", "plain"),
    "k":  ("stop", "velar",   "plain"),
    # glottal-aspirated stops
    "ph": ("stop", "labial",  "aspirated_glottal"),
    "th": ("stop", "coronal", "aspirated_glottal"),
    "kh": ("stop", "velar",   "aspirated_glottal"),
    # ejective stops
    "p'": ("stop", "labial",  "ejective"),
    "t'": ("stop", "coronal", "ejective"),
    "k'": ("stop", "velar",   "ejective"),
    # velar/uvular-aspirated stops — Q2 centerpiece
    "pȟ": ("stop", "labial",  "aspirated_uvular"),
    "tȟ": ("stop", "coronal", "aspirated_uvular"),
    "kȟ": ("stop", "velar",   "aspirated_uvular"),
    # affricates (postalveolar)
    "č":  ("affricate", "postalveolar", "plain"),
    "čh": ("affricate", "postalveolar", "aspirated_glottal"),
    "č'": ("affricate", "postalveolar", "ejective"),
    # fricatives — secondary (documented, not a primary target)
    "s":  ("fricative", "alveolar",     "plain"),
    "š":  ("fricative", "postalveolar", "plain"),
    "ȟ":  ("fricative", "uvular",       "plain"),
    "s'": ("fricative", "alveolar",     "ejective"),
    "š'": ("fricative", "postalveolar", "ejective"),
    "ȟ'": ("fricative", "uvular",       "ejective"),
}
# normalize the keys so they match normalize_orthography() output exactly
SOUND_TABLE = {normalize_orthography(k): v for k, v in _SOUND_TABLE_RAW.items()}


def to_category(manner: str, laryngeal: str) -> str:
    """Praat-sound_type-aligned coarse category (both aspirations → 'aspirated')."""
    lar = "aspirated" if laryngeal.startswith("aspirated") else laryngeal
    return f"{manner}_{lar}"


OUT_COLUMNS = [
    # auto-filled by this script
    "sound", "sound_ipa", "target", "word", "gloss", "position",
    "manner", "place", "laryngeal", "category",
    # left blank for the team to fill (linguistic judgement / lookup)
    "following_vowel", "stress", "documented_asp", "probe",
    "provenance", "preceding_seg", "notes",
]
_AUTO = {"sound", "sound_ipa", "target", "word", "gloss", "position",
         "manner", "place", "laryngeal", "category"}


# ── parsing ──────────────────────────────────────────────────────────────────
def parse_sound_label(raw: str):
    """Return (orthographic_sound_RAW, ipa). <…> wraps orthography; […] wraps IPA."""
    raw = raw.strip()
    if "<" in raw and ">" in raw:
        ortho = raw[raw.index("<") + 1: raw.index(">")].strip()
        ipa = (raw[:raw.index("<")] + raw[raw.index(">") + 1:]).strip()
    elif "[" in raw and "]" in raw:
        ipa = raw[raw.index("[") + 1: raw.index("]")].strip()
        ortho = (raw[:raw.index("[")] + raw[raw.index("]") + 1:]).strip()
    else:
        ortho, ipa = raw, ""
    return ortho, ipa


def split_word_gloss(cell: str):
    """'orthography (gloss)' → (word_RAW, gloss_RAW). Splits on first '('. Keeps
    parens nested inside the gloss."""
    cell = cell.strip()
    if not cell:
        return "", ""
    i = cell.find(" (")
    if i == -1:
        i = cell.find("(")
    if i == -1:
        return cell, ""
    word = cell[:i].strip()
    gloss = cell[i:].strip()
    if gloss.startswith("("):
        gloss = gloss[1:]
    if gloss.endswith(")"):
        gloss = gloss[:-1]
    return word, gloss.strip()


# ── driver ───────────────────────────────────────────────────────────────────
def transform(input_path: Path):
    """Yield output dict-rows; return (rows, report)."""
    rows = []
    edits = set()          # (raw, normalized) where normalization changed something
    missing = {}           # sound -> count, for sounds absent from SOUND_TABLE
    per_cell = {}          # (sound, position) -> count, for a coverage sanity print

    with input_path.open(encoding="utf-8-sig", newline="") as fh:
        current_sound_raw = None
        for rec in csv.reader(fh):
            c0 = rec[0].strip() if len(rec) > 0 else ""
            c1 = rec[1] if len(rec) > 1 else ""
            c2 = rec[2] if len(rec) > 2 else ""
            if not c0 and not c1.strip() and not c2.strip():
                continue  # family-separator row
            if c0:
                current_sound_raw = c0
            if current_sound_raw is None:
                continue

            ortho_raw, ipa = parse_sound_label(current_sound_raw)
            sound = normalize_orthography(ortho_raw)
            if sound != ortho_raw:
                edits.add((ortho_raw, sound))

            entry = SOUND_TABLE.get(sound)
            if entry is None:
                missing[sound] = missing.get(sound, 0) + 1
                manner = place = laryngeal = category = ""
            else:
                manner, place, laryngeal = entry
                category = to_category(manner, laryngeal)

            for position, cell in (("initial", c1), ("intervocalic", c2)):
                word_raw, gloss_raw = split_word_gloss(cell)
                word = normalize_orthography(word_raw)
                if not word:
                    continue
                if word != word_raw:
                    edits.add((word_raw, word))
                per_cell[(sound, position)] = per_cell.get((sound, position), 0) + 1

                row = {c: "" for c in OUT_COLUMNS}
                row.update(
                    sound=sound, sound_ipa=nfc(ipa), target=sound,
                    word=word, gloss=nfc(gloss_raw), position=position,
                    manner=manner, place=place, laryngeal=laryngeal,
                    category=category,
                )
                rows.append(row)

    return rows, {"edits": edits, "missing": missing, "per_cell": per_cell}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="the hand-kept word sheet (.csv)")
    ap.add_argument("-o", "--output", type=Path,
                    default=Path("config/words_metadata.csv"),
                    help="machine-friendly output (default: config/words_metadata.csv)")
    ap.add_argument("--report", action="store_true",
                    help="print every normalization edit, not just the summary")
    args = ap.parse_args(argv)

    if not args.input.exists():
        ap.error(f"input not found: {args.input}")

    rows, report = transform(args.input)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    # ── summary to stderr (always) ──
    sounds = sorted({r["sound"] for r in rows})
    blank_cols = [c for c in OUT_COLUMNS if c not in _AUTO]
    print(f"[normalize_wordlist] wrote {len(rows)} word-rows "
          f"({len(sounds)} sounds) → {args.output}", file=sys.stderr)
    print(f"[normalize_wordlist] auto-filled: {sorted(_AUTO)}", file=sys.stderr)
    print(f"[normalize_wordlist] left BLANK for you: {blank_cols}", file=sys.stderr)
    print(f"[normalize_wordlist] normalization edits: {len(report['edits'])}",
          file=sys.stderr)
    if report["missing"]:
        print("[normalize_wordlist] WARNING — sounds NOT in SOUND_TABLE "
              "(manner/place/category left blank):", file=sys.stderr)
        for s, n in sorted(report["missing"].items()):
            print(f"    {s!r}  ×{n}", file=sys.stderr)
    # cells that didn't land the expected 2 words/position (data-entry sanity)
    odd = {k: v for k, v in report["per_cell"].items() if v != 2}
    if odd:
        print("[normalize_wordlist] note — (sound, position) cells without exactly "
              "2 words:", file=sys.stderr)
        for (s, pos), n in sorted(odd.items()):
            print(f"    {s!r:>6} {pos:<12} ×{n}", file=sys.stderr)
    if args.report and report["edits"]:
        print("[normalize_wordlist] edits (raw → normalized):", file=sys.stderr)
        for raw, norm in sorted(report["edits"]):
            print(f"    {raw!r}  →  {norm!r}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
