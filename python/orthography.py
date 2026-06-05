"""Shared Lakota orthography normalization - THE join contract.

Both `normalize_wordlist.py` (authoring side) and `merge_metadata.py` (pipeline side)
import `normalize_orthography()` so the two halves of the word-grain join canonicalize
byte-for-byte identically. If this function ever forks, the join silently breaks - so it
lives here, shared, on purpose. See CLAUDE.md token-data-model.

The hand-kept wordlist is pervasively NFD (base letter + combining diacritic) with mixed
apostrophe characters and a script-g vs regular-g lookalike; this folds all of that to one
canonical form, then NFC-composes.
"""

import unicodedata

CANONICAL_APOSTROPHE = "'"  # U+0027

# every character a human or an export might have used for the ejective mark
APOSTROPHE_VARIANTS = {
    "‘",  # left single quote
    "’",  # right single quote (LLC-standard Lakota saltillo)
    "ʼ",  # modifier letter apostrophe
    "ˈ",  # modifier letter vertical line (seen in the wordlist's "sˈe")
    "ʹ",  # modifier letter prime
    "′",  # prime
}

# NFC alone won't merge these: the BASE letter differs (script-g vs regular-g).
BASE_FOLDS = {
    "ɡ": "g",  # latin small letter script g -> g (so NFC composes one ǧ)
}


def normalize_orthography(s):
    """Canonicalize a Lakota orthographic string for exact-match joins. Idempotent.

    Run this on BOTH sides of any word comparison (the wordlist AND the Praat TextGrid
    word labels). The canonical apostrophe choice is internal; what matters is that both
    sides pass through here.
    """
    if not s:
        return s
    out = []
    for ch in s:
        if ch in APOSTROPHE_VARIANTS:
            out.append(CANONICAL_APOSTROPHE)
        elif ch in BASE_FOLDS:
            out.append(BASE_FOLDS[ch])
        else:
            out.append(ch)
    s = unicodedata.normalize("NFC", "".join(out))
    return " ".join(s.split())


def nfc(s):
    """Light touch for non-join fields (glosses): NFC + whitespace collapse only."""
    if not s:
        return s
    return " ".join(unicodedata.normalize("NFC", s).split())
