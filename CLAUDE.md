# CLAUDE.md — Lakota Obstruents Acoustic Phonetics Pipeline

## project overview

descriptive acoustic phonetics study of the Lakota (Oglala, Pine Ridge) obstruent system. two young revitalization-generation speakers, elicited citation forms in carrier phrase. NOT a statistical generalization study — n=2, analyzed per speaker, never pooled.

### targets
- coronal stop series: /t tʰ tȟ tʼ/ (plain, glottal-aspirated, velar/uvular-aspirated, ejective)
- affricate series: /tʃ tʃʰ tʃʼ/
- secondary place check: /p k/

~35-50 distinct words, ~5 reps each, 2 speakers.

### notation
- `[ ]` phonetic, `/ /` phonemic, `⟨ ⟩` orthographic
- ⟨ȟ⟩ = velar/uvular frication; ⟨tʰ⟩/⟨th⟩ = glottal aspiration; ⟨tȟ⟩ = velar/uvular aspiration; ⟨tʼ⟩/⟨t'⟩ = ejective

## recording format

one WAV per speaker — full session recording of controlled carrier-phrase elicitation. mono WAV, >=44.1 kHz / 16-bit, sound booth.

## research questions

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
raw WAV (read-only)
  -> manual pre-segmentation: word + rep + segment intervals in Praat
  -> landmark annotation: helper script guides per-segment point placement
  -> measurement extraction: frozen Praat script -> CSV
  -> Python pipeline: merge metadata -> validate -> derive -> analyze -> figures
  -> spectrogram export: separate compute-heavy Praat script for images
```

### stack
- **Praat**: annotation helper, measurement extraction, spectrogram export
- **Python 3.12**: pandas, numpy, scipy, matplotlib/seaborn, scikit-learn, PyYAML
- **no R / lme4** (inappropriate for n=2)
- **no forced alignment** (no Lakota model; all boundaries human-placed/verified)

## TextGrid tier structure (7 tiers)

| Tier | Type     | Name       | Content                                                |
|------|----------|------------|--------------------------------------------------------|
| 1    | interval | word       | orthographic word (e.g., "thezi")                      |
| 2    | interval | rep        | repetition (e.g., "thezi.r1")                          |
| 3    | interval | segment    | target segment (e.g., "thezi.r1.s1"); multiple per rep |
| 4    | interval | fric       | affricate frication interval (manual)                  |
| 5    | interval | vmid       | vowel steady-state interval (manual)                   |
| 6    | point    | landmarks  | t_clo, t_burst, t_burst_end, t_voi, t_vend, t_glot_rel, t_pvend |
| 7    | point    | metadata   | ok:{sound_type}, skip, garbage                         |

containment: reps within words, segments within reps, landmarks within segments (by time overlap with epsilon tolerance). adapted from vowel_analysis.praat nesting logic.

## point landmarks (tier 6, full names)

- `t_clo` — closure onset (optional; VCV only)
- `t_burst` — release/burst onset
- `t_burst_end` — burst offset (stops only, NOT affricates)
- `t_voi` — voicing onset (first modal glottal pulse)
- `t_vend` — following-vowel offset
- `t_glot_rel` — glottal-release transient (ejectives only)
- `t_pvend` — preceding-vowel offset (conditional)

## sound types (determines landmark subset)

| type                 | landmarks                                                |
|----------------------|----------------------------------------------------------|
| stop_plain           | t_clo(opt), t_burst, t_burst_end, t_voi, t_vend         |
| stop_aspirated       | t_clo(opt), t_burst, t_burst_end, t_voi, t_vend         |
| stop_ejective        | t_clo(opt), t_burst, t_burst_end, t_glot_rel, t_voi, t_vend |
| affricate_plain      | t_clo(opt), t_burst, t_voi, t_vend                      |
| affricate_aspirated  | t_clo(opt), t_burst, t_voi, t_vend                      |
| affricate_ejective   | t_clo(opt), t_burst, t_glot_rel, t_voi, t_vend          |

## measurement battery (~55 columns)

**temporal**: VOT (signed), closure_dur, burst_dur, aspiration_dur, gap_dur, glottal_oral_interval (signed), vowel_dur, fric_dur
**voiced-closure** (when t_clo present): voiced_closure_prop, voiced_closure_onset_ms
**intensity**: burst peak, vowel-onset mean, burst-to-vowel ratio, aspiration mean, fric mean, gap RMS, gap_is_silent
**spectral moments** (FFT, power=2): burst 4 moments, aspiration 4, frication 4
**formants**: F1/F2/F3 at onset (W_von=30ms), F1/F2/F3 at midpoint (W_vmid center)
**f0**: onset value, contour (semicolon-separated, 10ms steps)
**H1-H2** (uncorrected): from Spectrum of W_von
**HNR**: from Harmonicity of W_von
**jitter/shimmer**: from PointProcess over vowel

## token data model

`token_id` = `{speaker}_{word}_{target_short}_{rep}`

columns: token_id, speaker, word, gloss, rep, target, category, place, position, following_vowel, stress, documented_asp (/C_e/ only), probe (semicolon-separated), provenance, preceding_seg, notes

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
config/          per-speaker settings + token metadata
data/raw/        read-only WAVs (one per speaker)
data/annotations/ TextGrids
data/derived/    extraction CSVs, merged tables, validation reports
praat/           00_create_textgrids, 01_annotate_helper, 02_extract_measurements, 03_export_spectrograms
python/          pipeline modules (run_pipeline, config_loader, load/merge/validate/derive/analyze)
figures/         q1-q4 analysis figures + spectrograms
output/          q1-q4 summary tables
```
