# Lakota Obstruents — Acoustic Phonetics Pipeline

This repository holds the tools and data for an acoustic study of Lakota consonants
(plain, aspirated, and ejective stops and affricates) produced by two speakers. It
takes you from a raw recording all the way to measurements and figures.

The workflow has two halves:

- **Annotation** (done in Praat): cut the recording into words, then mark a small
  number of points on each sound. This half needs no programming and is written so
  that anyone who has taken a phonetics course can do it.
- **Analysis** (done in Python): turn the marks into measurements, check them, and
  make tables and figures. This half is run by the team member handling the code.

---

## Part 1 — Instructions

### What you need first

1. **Praat** (the free phonetics program). Download it from <https://www.praat.org>
   and unzip it anywhere. You run it by double-clicking `Praat.exe`.
2. The recording for your speaker, as a single `.wav` file.
3. (Analysis half only) **Python** and a few packages. You do **not** need to install
   or know anything about Python first — just **double-click `setup.cmd`** in this folder.
   It installs Python if it is missing, builds an isolated environment, and installs the
   packages, all by itself and without administrator rights. Run it once; re-run it any
   time it complains. (Under the hood it uses Python 3.12 and the versions pinned in
   `requirements.txt`.)

### How to run any Praat script in this repo

1. Open Praat. Two windows appear; use the one titled **"Praat Objects"**.
2. In its menu bar, click **Praat → Open Praat script…** and choose the script
   (for example `praat/00_slice_words.praat`). Always open the script this way, from
   its place inside the repo — that is how it finds the data folders.
3. A script window opens. In its menu bar, click **Run → Run** (or press Ctrl+R).
4. A settings box appears. The scripts work out where the repo's folders are on their
   own, so the boxes only ask for the speaker name and a few settings — no file paths
   to type or browse to. Fill them in and click **OK**.

That is all there is to it. The steps below tell you which script to run and what
to put in the boxes. (If a script stops with a message about not finding the `data/`
folder, you opened it from outside the repo — re-open it via the menu above.)

### Step 1 — Put the recording in place

Copy your speaker's recording into `data/raw/` and name it after the speaker, for
example `data/raw/S1.wav`. Leave this file alone afterwards; it is the master copy.

### Step 2 — Mark the words (the only by-hand step)

You will draw a box around each word in the recording. This is the one thing the
scripts cannot do for you.

1. In Praat Objects, click **Open → Read from file…** and open your `.wav`.
2. With the sound selected, click **Annotate → To TextGrid…**.
3. In the box labelled **"All tier names"**, type `word`. Clear the
   **"Which … are point tiers?"** box so it is empty. Click **OK**.
4. Select both the Sound and the new TextGrid (hold Ctrl and click each), then
   click **View & Edit**.
5. In the editor, for each spoken word: click and drag to highlight the word,
   press **Enter** to add a boundary at each edge, click inside the word's box on
   the `word` tier, and type the word (its normal Lakota spelling).
6. When every word is boxed and labelled, click **File → Save TextGrid as text
   file…** and save it as `data/session_textgrids/S1.TextGrid` (use your speaker's
   name).

You only need the words. You do **not** mark repetitions or individual sounds here —
the scripts handle that next, on smaller, easier-to-read files.

### Step 3 — Cut the recording into word files

Run `praat/00_slice_words.praat`. In the settings box:

- **Speaker id** — `S1` (or your speaker's name). The script uses this to find
  `data/raw/S1.wav` and `data/session_textgrids/S1.TextGrid`, and to choose where to
  write the word files (`data/words/S1/`).
- **Word tier** — `1`.
- **Slice padding (ms)** — `50` is fine.

This creates one small `.wav` and `.TextGrid` per word inside `data/words/S1/`, plus
a `words_manifest.csv` listing them. It never overwrites work you have already done,
so it is safe to run again if you add more words later.

### Step 4 — Mark the sounds

Run `praat/01_annotate_helper.praat`. In the settings box, set **Speaker id** (for
example `S1`) and click OK; it opens that speaker's word files automatically.

The script opens each word file and walks you through it. **Drag the first popup
window off to the side** so it does not cover the sound editor; Praat keeps later
popups in that spot. Use the **Exit** button to stop — do not close the editor
window itself.

For each word you will, in order:

1. **Mark the repetitions.** Highlight each time the speaker says the word, and
   click *Mark*. Click *Done* when finished.
2. **Mark the target sound(s).** Inside each repetition, highlight the consonant you
   are studying plus the vowel right after it, and click *Mark*.
3. **Place the marks** on each target sound. The popup tells you, in plain language,
   what to look for and where to click. You can *Skip* any mark you cannot see,
   *Redo* if you want to start the sound over, or mark the whole thing *Garbage* if
   the recording is bad.

Everything saves automatically as you accept each sound. If you stop and come back,
the script skips what you already finished (leave **Resume** ticked).

### Step 5 — Pull out the measurements (analysis half)

Run `praat/02_extract_measurements.praat` with the same **Speaker id**. It writes
one row per measured sound to `data/derived/extraction/measurements_S1.csv`. This
file is plain text and opens cleanly in Excel.

### Step 5b — Better formants with FastTrack (analysis half)

The main measurements use a single formant setting. For more accurate vowel formants we also
run **FastTrack** (a bundled add-on that tries many settings per vowel and keeps the best one).
These become the study's main formant numbers; the Step 5 ones are kept alongside for comparison.

1. Open `praat/vendor/FastTrack/Fast Track/functions/02b_formants.praat` (Praat → Open Praat
   script…) and **Run**. Leave **Mode** on `extract`, set **Speaker id**, and make sure the
   FastTrack settings match `config/pipeline_config.yaml` (the low/high frequency range is set
   per speaker by voice height). It writes `data/derived/extraction/formants_S1.csv`.
2. (Optional check) After running the Python pipeline once (Step 7), it writes a short list of
   sounds to re-check. Re-open `02b_formants.praat`, switch **Mode** to `images`, and Run from
   the Praat window: it saves side-by-side comparison pictures for just those sounds to
   `figures/formant_winners/S1/`, so you can confirm FastTrack picked sensible tracks.

This is its own step (like the pictures below) because it does a lot of analysis per vowel.

### Step 6 — Pictures (optional, run any time)

Run `praat/03_export_spectrograms.praat` to save a figure for each measured sound.
In the settings box, set **Speaker id** (for example `S1`); the rest can stay at their
defaults.
Each figure shows one target sound with its marks drawn in (closure/burst/voicing/
vowel-end, the ejective pop, and the vowel-middle stretch), saved to
`figures/spectrograms/<speaker>/`.

The figure is built from a stack of **panels** you choose. The **Panels** box takes
a space-separated list, drawn top to bottom — any of `oscillogram`, `spectrogram`,
`pitch`, `intensity` (default: `oscillogram spectrogram`). **Layout** picks whether
they go in one combined image (*stacked*, sharing a time axis) or one image per panel
(*separate*). You can also tick **Overlay formants on spectrogram**. The panel
heights/width are adjustable if a figure feels cramped or stretched, and
**Minimum window** keeps the time span from zooming in so far the spectrogram breaks
into discrete "stars".

By default **Preview first** is on: it draws a single example (shown in the Picture
window and saved), then asks whether to render the rest — so you can check the layout
before committing to the whole directory.

This is slow, so it is kept separate and can be run whenever you like. By default it
only draws sounds you have *accepted* and skips images that already exist, so it is
safe to re-run after annotating a few more words. Tick **Overwrite existing images**
to redraw everything, or untick **Accepted only** to also picture skipped/garbage
sounds (useful for double-checking them).

### Step 7 — Analyse (Python)

The Python tools in `python/` merge the measurements with the word list, run the
quality checks, and produce the tables and figures. See that folder's notes when it
is ready. *(Still being built.)*

---

## Part 2 — The marks, explained

When you mark a sound, you place these points. You do not need to know the technical
names; the popups explain each one as you go. This table is here for reference.

| Mark | Plain meaning |
| --- | --- |
| **closure start** (`t_clo`) | Where the consonant goes silent — the previous vowel stops and the line goes flat. Only if a vowel comes right before; skip at the start of a word. (Fricatives have no closure — the helper won't ask for this.) |
| **release / burst** (`t_burst`) | The sharp pop where the consonant opens up. For *ch*-type sounds and fricatives (s, š, ȟ), where the hissy noise starts instead. |
| **ejective pop** (`t_glot_rel`) | Ejectives only: the small second pop just after the main release. |
| **voicing start** (`t_voi`) | Where the following vowel's buzzing begins — the first steady, repeating wave. |
| **vowel end** (`t_vend`) | Where the following vowel stops. |
| **vowel middle** (`vmid`) | A highlighted stretch in the calm center of the vowel. |
| **earlier vowel end** (`t_pvend`) | Usually skipped; only if a vowel from the previous word runs into this one. |

**Sound types** you choose from the menu: plain / aspirated / ejective **stop**
(p, t, k), plain / aspirated / ejective **affricate** (the *ch* sound), and plain /
ejective **fricative** (s, š, ȟ and their ejectives). For a fricative the helper asks
where the hiss starts instead of a burst, and skips the closure mark. The menu spells
out what each one means.

---

## Part 3 — Working as a team of two

Because every word is its own small file, two people can annotate at the same time
without stepping on each other. The simplest split is for each person to take a set
of word files (or half of each speaker's words) and annotate only those. Avoid having
two people open and save the *same* word file. When you are done, the word files can
be pooled back together for analysis.

---

## Part 4 — Opening the spreadsheets in Excel

- `measurements_S1.csv` and `config/token_metadata.csv` open cleanly by
  double-clicking — they are saved so Excel reads the accented Lakota letters
  correctly.
- `words_manifest.csv` keeps the full Lakota spelling of each word, which can confuse
  a plain double-click. If the letters look wrong, open it through Excel's
  **Data → From Text/CSV** menu instead, which detects the format automatically.

---

## Part 5 — Folder map

```
data/
  raw/                 Master recordings, one per speaker (never edited).
  session_textgrids/   Your word-boundary TextGrids from Step 2.
  words/<speaker>/     One small WAV + TextGrid per word, plus words_manifest.csv.
  derived/             Measurements and analysis outputs (made by the scripts).
praat/
  00_slice_words.praat           Step 3: cut the recording into word files.
  01_annotate_helper.praat       Step 4: mark the sounds.
  02_extract_measurements.praat  Step 5: pull out the measurements.
  03_export_spectrograms.praat   Step 6: save spectrogram images.
python/                Step 7: the analysis tools.
config/
  pipeline_config.yaml   Settings (per-speaker pitch range, etc.).
  token_metadata.csv     The word list with each sound's details, filled in by the team.
figures/  output/        Where figures and result tables are saved.
```

---

## Part 6 — About the study

This is a descriptive case study of two Lakota (Oglala, Pine Ridge) speakers reading
words in a carrier phrase. It characterises how these two speakers produce their
stops and affricates — plain versus aspirated versus ejective — and compares them to
published descriptions. It looks at four questions: how plain stops are made, where
the "guttural" aspiration sits, how the *ch* sounds differ from each other, and how
strong the ejectives are.

Because there are only two speakers, the findings describe **these speakers**; they
are not claims about Lakota in general. The analysis keeps the two speakers separate
and never pools them.

The scripts and analysis code are research tools; their use is documented in the
paper's Methods section, and a portion of the measurements is re-checked by hand
against the automated output to confirm the numbers are trustworthy.

---

## Requirements

- **Praat** 6.4 or newer (developed against 6.4.62).
- **Python** 3.12, with the packages pinned in `requirements.txt`.
- Recordings: mono WAV, 44.1 kHz or higher, 16-bit, ideally from a sound booth.
