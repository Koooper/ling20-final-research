# Vendored FastTrack

FastTrack — (nearly) automatic formant tracking for Praat, by Santiago Barreda.
Upstream: https://github.com/santiagobarreda/FastTrack — MIT License (see `LICENSE`).

- Vendored commit: `999e3367f47484f7e26e3d8ba7e04b2995384da5` (2025-10-27).
- Paper: Barreda, S. (2021). Fast Track: fast (nearly) automatic formant-tracking using Praat.
  *Linguistics Vanguard* 7(1). https://doi.org/10.1515/lingvan-2020-0051

Everything under `Fast Track/` is **upstream and unmodified** EXCEPT one repo-authored file:

    Fast Track/functions/02b_formants.praat   <- OURS (Lakota pipeline canonical-formant pass)

It lives inside `functions/` because Praat resolves `include` relative to the main script, and
FastTrack's nested includes assume that location. `UPSTREAM_README.md` is FastTrack's own README.

To update FastTrack: re-copy upstream `Fast Track/`, then restore `02b_formants.praat` and
re-check that `utils/trackAutoselectProcedure.praat`'s signature + the globals `findError.praat`
reads are unchanged (02b sets them explicitly and calls `@trackAutoselect`).
