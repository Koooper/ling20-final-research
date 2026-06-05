# CLAUDE.md — Lakota Obstruents Acoustic Phonetics Pipeline

## project overview

descriptive acoustic phonetics study of the Lakota (Oglala, Pine Ridge) obstruent system. two young revitalization-generation speakers, elicited citation forms in carrier phrase. NOT a statistical generalization study — n=2, analyzed per speaker, never pooled.

### targets
- coronal stop series: /t tʰ tȟ tʼ/ (plain, glottal-aspirated, velar/uvular-aspirated, ejective)
- affricate series: /tʃ tʃʰ tʃʼ/
- secondary place check: /p k/ (+ full labial/velar series pʰ pʼ pȟ kʰ kʼ kȟ now elicited)
- fricatives /s š ȟ sʼ šʼ ȟʼ/ — SECONDARY tier: document properties (frication moments,
  formant transitions), not a primary research target; they pattern per documentation

~35-50 distinct words, ~5 reps each, 2 speakers.

### notation
- `[ ]` phonetic, `/ /` phonemic, `⟨ ⟩` orthographic
- ⟨ȟ⟩ = velar/uvular frication; ⟨tʰ⟩/⟨th⟩ = glottal aspiration; ⟨tȟ⟩ = velar/uvular aspiration; ⟨tʼ⟩/⟨t'⟩ = ejective

## recording format

one WAV per speaker — full session recording of controlled carrier-phrase elicitation. mono WAV, >=44.1 kHz / 16-bit, sound booth.

## research questions

This is a documentation study: the four questions are LENSES over measures taken across the
whole inventory, NOT bins tokens get assigned to. Dispatch is property-based, not probe-routed —
every measure runs for every token its landmarks+properties support (else NA-with-reason), and
each Q is a non-exclusive VIEW selecting/grouping by linguistic property (manner/laryngeal/place/
position). A token feeds every view it qualifies for; `full_inventory` holds them all. See the
token-data-model + the analysis-dispatch notes.

**Q1 — plain stop realization + aspiration contrast**
how are plain voiceless stops realized in word-initial and stressed positions? unaspirated vs aspirated stops are documented as contrastive in dictionary entries — does the acoustic data support this? preliminary [k] vs [kʰ] data needs further evaluation (velar place secondary to coronal but now explicitly in scope).
measures: VOT, voiced-closure-prop, closure-dur by position, per speaker.

**Q2 — guttural aspiration localization**
where exactly are the "guttural" (velar/uvular) aspirations being realized? how velar vs uvular are they, and does it vary by vowel context? the documented allophonic conditioning (velar before back vowels, glottal before front) needs acoustic verification via spectral moments. /C_e/ lexicalization question folds in here — do /e/-context tokens pattern as gradient coarticulation or lexically fixed?
measures: COG + spectral moments of aspiration noise by following vowel; /e/-tokens item-based with `documented_asp`.

**Q3 — affricate differentiation**
how acoustically distinct are the three forms of ⟨č⟩ — plain /tʃ/, aspirated /tʃʰ/, ejective /tʃʼ/? existing descriptions are impressionistic; the affricate is noisy and the contrasts need quantification.
measures: VOT/gap + frication COG by category. uneven cell sizes expected (plain & ejective affricates rarer).

**Q4 — ejective canonicality**
how strong and canonical are the ejectives? are they "true" glottalic egressives (strong burst + silent gap + raised f0) or coarticulation of a stop with a voiceless glottal plosive (glottal-reinforced pulmonic)?
measures: silent_gap, burst_intensity_rel, f0_onset, H1-H2, HNR, jitter, shimmer.

## pipeline architecture

```
session WAV (read-only, one per speaker)
  -> MANUAL pre-step (the only one): mark WORD intervals on a session word tier
  -> 00_slice_words.praat: slice each word into data/words/{speaker}/{NN}_{word}.wav
                           + blank 6-tier per-word TextGrid (word tier pre-filled)
  -> 01_annotate_helper.praat: walk per-word files; per file, 3 phases:
       reps (drag-select -> auto r1,r2..) -> segments (auto s1,s2..) -> landmarks
  -> 02_extract_measurements.praat: frozen battery -> measurements_{speaker}.csv
  -> 02b_formants.praat (vendored FastTrack): canonical formants -> formants_{speaker}.csv
  -> Python pipeline: merge metadata -> merge formants (by token_id) -> validate
                      -> derive -> analyze -> figures
  -> 03_export_spectrograms.praat: separate compute-heavy Praat script for images
```

The session is sliced into per-word WAVs so annotation never zooms around a
multi-minute session. Each per-word file IS one word; the word identity lives on
its (pre-filled) tier 1. Reps and segments are auto-numbered by the helper in
time order (r1/r2.., s1/s2..); their linguistic identity is resolved via the
metadata CSV join, not the positional TextGrid labels.

### stack
- **Praat**: annotation helper, measurement extraction, spectrogram export
- **Python 3.12**: pandas, numpy, scipy, matplotlib/seaborn, scikit-learn, PyYAML
- **no R / lme4** (inappropriate for n=2)
- **no forced alignment** (no Lakota model; all boundaries human-placed/verified)

## TextGrid tier structure (6 tiers, per-word file)

| Tier | Type     | Name       | Content                                                |
|------|----------|------------|--------------------------------------------------------|
| 1    | interval | word       | orthographic word; single whole-file interval, pre-filled by slicer |
| 2    | interval | rep        | repetition (auto-labeled r1, r2, ...)                  |
| 3    | interval | segment    | target segment (auto-labeled s1, s2, ...); multiple per rep |
| 4    | interval | vmid       | vowel steady-state interval (manual)                   |
| 5    | point    | landmarks  | t_clo, t_burst, t_voi, t_vend, t_glot_rel, t_pvend     |
| 6    | point    | metadata   | ok:{sound_type}, skip, garbage                         |

Each per-word file has tier 1 = one interval (the word). Reps/segments marked by
the helper. containment: segments within reps, landmarks within segments (time
overlap, epsilon tolerance, closed-right since t_vend often sits on seg_end).
The session word-tier TextGrid (pre-slice) lives in data/session_textgrids/.
(No fric tier and no t_burst_end: affricate deep-dive is out of scope; the
burst->voicing window captures aspiration, affricate AND fricative frication alike.)

## point landmarks (tier 5, full names)

- `t_clo` — closure onset (optional; VCV only)
- `t_burst` — release/burst onset (for affricates, frication onset)
- `t_voi` — voicing onset (first modal glottal pulse)
- `t_vend` — following-vowel offset
- `t_glot_rel` — glottal-release transient (ejectives only)
- `t_pvend` — preceding-vowel offset (conditional)

## sound types (uniform landmark set; ejectives add t_glot_rel)

| type                 | landmarks                                       |
|----------------------|-------------------------------------------------|
| stop_plain           | t_clo(opt), t_burst, t_voi, t_vend             |
| stop_aspirated       | t_clo(opt), t_burst, t_voi, t_vend             |
| stop_ejective        | t_clo(opt), t_burst, t_glot_rel, t_voi, t_vend |
| affricate_plain      | t_clo(opt), t_burst, t_voi, t_vend             |
| affricate_aspirated  | t_clo(opt), t_burst, t_voi, t_vend             |
| affricate_ejective   | t_clo(opt), t_burst, t_glot_rel, t_voi, t_vend |
| fricative_plain      | t_burst(=frication onset), t_voi, t_vend        |
| fricative_ejective   | t_burst(=frication onset), t_glot_rel, t_voi, t_vend |

Fricatives have NO t_clo (no silent closure); t_burst marks frication onset. They are a
SECONDARY "document the properties" tier (frication COG/moments + formant transitions),
not a primary research target. Same landmark-driven battery, no fricative-specific code.

## measurement battery (44 columns)

**temporal**: VOT (signed), closure_dur, glottal_oral_interval (signed), vowel_dur. (noise/aspiration duration == VOT, not emitted separately.)
**voiced-closure** (when t_clo present): voiced_closure_prop, voiced_closure_onset_ms
**intensity**: burst peak (t_burst→+20ms), vowel-onset mean, burst-to-vowel ratio, noise mean, noise_is_silent
**spectral moments** (FFT, power=2): noise 4 moments over t_burst→t_voi (= aspiration COG for aspirated, frication COG for affricates AND fricatives, flat for ejective gaps)
**formants** (single-ceiling, co-compat → `sc_f1/2/3_onset_hz`, `sc_f*_mid_hz`): F1/F2/F3 at onset (W_von=30ms) + midpoint (vmid center). The CANONICAL formants (`f1/2/3_onset_hz`, `f*_mid_hz`) come from FastTrack (02b), joined in Python — see the FastTrack subsystem note.
**f0**: onset value, contour (semicolon-separated, 10ms steps)
**H1-H2** (uncorrected): from Spectrum of W_von
**HNR**: from Harmonicity of W_von
**jitter/shimmer**: from PointProcess over vowel

## FastTrack formant subsystem (canonical formants)

Formants are measured by FastTrack (Barreda 2021, vendored MIT at `praat/vendor/FastTrack/`),
which sweeps many ceilings per vowel and picks the smoothest winner — better than 02's single
ceiling, especially across high/low vowels. FastTrack is CANONICAL: its values own the plain
names `f1/2/3_onset_hz` + `f*_mid_hz` that derive/analyze read. 02's single-ceiling formants
ride alongside as `sc_*` for a methods comparison (`output/{spk}/formant_method_comparison.csv`).

- **Pass:** `praat/vendor/FastTrack/Fast Track/functions/02b_formants.praat` (the ONE
  repo-authored file inside the vendored tree — everything else there is upstream). It lives
  there because Praat resolves `include` relative to the main script and FastTrack's nested
  includes assume that location. Two modes: `extract` (headless → `formants_{spk}.csv`) and
  `images` (GUI → comparison PNGs for the 12% hand-check subset only).
- **Output** `data/derived/extraction/formants_{speaker}.csv` (token_id-keyed): canonical onset
  + mid F1-F3, trajectory at 20/50/80%, per-token DCT coefficients (`f*_c0..`), and diagnostics
  `ft_ceiling_hz` / `ft_minerror` / `ft_ceiling_at_bound`.
- **Join:** `python/load_formants.py` `merge_formants()` left-joins by token_id — the ONLY
  token-grain join (everything else is word-grain). token_id MUST match 02 exactly; drift leaves
  canonical formants NaN → coverage 'missing'. The pass is optional: if `formants_{spk}.csv` is
  absent, canonical formants are all-NA and the pipeline still runs (validate warns).
- **Config:** per-speaker `ft_low_hz`/`ft_high_hz` (VTL-dependent sweep range) + global
  `analysis.fasttrack` (steps/coefficients/n_formants/buffer_ms) + `validation.ft_minerror_max`.
- **Edge gotcha:** FastTrack's 25ms window dead-zones vowel edges, where our onset window sits,
  so 02b extracts `[t_voi − buffer, t_vend + buffer]` (buffer_ms of real audio) with times preserved.
- **Validation flags:** `ft_ceiling_at_bound` (widen range), `ft_minerror > ft_minerror_max`
  (heuristic penalty / bad track), formant-row orphans, accepted tokens missing a formant row.

## token data model

`token_id` = `{speaker}_{filestem}_{rep}_{segment}` (e.g., `S1_07_pablu_r1_s1`).
Built by 02 from the per-word file stem, tier-2 rep label, tier-3 segment label. The
filestem is `{NN}_{safeword}`, where 00's `sanitize` maps every non-ASCII char to `_`
(č ȟ á ʼ → _), so the stem's word portion is LOSSY — you CANNOT recover orthography from
token_id. Uniqueness comes from the NN index, not the word.

**JOIN (two stages, word-grain — NOT by token_id):**
  1. `measurements.file` == `words_manifest.filename` (both are the `{NN}_{safeword}` stem)
     → recovers `words_manifest.word_label` (the raw, full-orthography TextGrid label).
  2. `normalize_orthography(word_label)` == `words_metadata.word`
     → attaches linguistic identity (target/category/place/position/probe/…).
Linguistic identity is authored at WORD grain in `config/words_metadata.csv` (one row per
sound×word×position; 84 rows, verified word-unique); speaker/rep/segment ride in from the
measurement side and merge_metadata fans word-grain rows out to tokens. There is NO
hand-authored token_id-keyed file (the old `config/token_metadata.csv` is superseded).
**Contract:** both `word_label` and `words_metadata.word` must pass through
`normalize_orthography()` before comparison (manifest is NFD + UTF-16 from Praat); and the
session-TextGrid word labels must be the SAME lexical strings as the sheet words (a typo, not
an encoding diff, is the one thing normalization can't save — surfaces as a merge orphan).
Assumes ONE target segment per word file; a stray s2 gets the same word-grain metadata and
must be caught in validate.

ENCODING: extraction CSV is ASCII-only (no orthography column) so Excel reads it cleanly. Full
orthography lives in `words_manifest.csv` (UTF-16, Praat-written — Python reads as UTF-16) and
`words_metadata.csv` (utf-8-sig). Python outputs use utf-8-sig.

`words_metadata.csv` columns — auto-filled by `normalize_wordlist.py`: sound, sound_ipa,
target, word, gloss, position, manner, place, laryngeal, category. Human-fill: following_vowel
+ stress (grouping refinements only — a view degrades to ungrouped if absent, never drops
tokens; derivable from word+position), documented_asp (/C_e/ only), provenance, preceding_seg,
notes. `probe` is OPTIONAL free-text (intended-focus annotation) — NOT a computation gate.

## per-speaker settings

- Formant ceiling: default 5000 Hz (adjustable)
- Formant number: 5
- Pitch floor/ceiling: set per speaker after calibration
- Intensity minimum pitch
- Recording floor (dB): measured from silence segment
- Silent gap threshold: recording_floor + offset dB

## data integrity rules

- human owns measurement layer — scripts never auto-place boundaries
- pipeline computes from committed landmarks only
- deterministic: same TextGrids + WAVs + frozen scripts = same numbers
- sanity assertions fail loud: VOT range, durations >= 0, COG range, formant ordering, token counts, no dup IDs
- validation harness: ~12% random subset hand-measured independently
- garbage reps tracked but excluded; pipeline handles n-1 reps gracefully
- raw data read-only; derived data regenerated from source

## scope guardrails

descriptive case study of two speakers. Oglala/Pine Ridge only, citation register only.
- allowed: characterize these speakers; within-speaker patterns; compare to documented descriptions (Buechel 1939; Ullrich 2008)
- NOT claimed: anything about Lakota generally, revitalization speakers as a class, other dialects, elder/L1 speakers, connected speech, generational change, causation
- no mixed models, no pooled analysis, no inferential generalization

## existing code references

- v3 annotation helper: `C:\Users\djjr6\Downloads\praat_vot_helper\01_mark_landmarks.praat`
- v3 extraction: `C:\Users\djjr6\Downloads\praat_vot_helper\02_extract_measurements.praat`
- vowel analysis (nesting logic reference): `C:\Users\djjr6\Downloads\vowel_analysis_output\vowel_analysis.praat`
- v2 variants in `Downloads\praat3\` and `Downloads\praat_scripts\`

## directory layout

```
config/                per-speaker settings + token metadata
data/raw/              read-only session WAVs (one per speaker), e.g. S1.wav
data/session_textgrids/ session TextGrids with hand-marked word tier (S1.TextGrid)
data/words/{speaker}/  sliced per-word WAV+TextGrid + words_manifest.csv (00 output;
                       holds the precious per-word annotations — do not blow away)
data/derived/          extraction + formants CSVs, merged tables, coverage, validation reports
praat/                 00_slice_words, 01_annotate_helper, 02_extract_measurements, 03_export_spectrograms
praat/vendor/FastTrack/ vendored FastTrack plugin (MIT) + the repo's 02b_formants.praat pass
python/                pipeline modules (run_pipeline, config_loader, load_extraction,
                       load_formants, merge_metadata, validate, derive, analyze, handcheck)
figures/               q1-q4 analysis figures + spectrograms + formant_winners/ (FastTrack images)
output/                q1-q4 summary tables + formant_method_comparison
```
