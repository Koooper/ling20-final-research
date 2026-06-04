# 00_slice_words.praat
#
# Stage A of the Lakota obstruents pipeline. Takes a full SESSION recording plus
# a session TextGrid whose WORD tier has been hand-segmented (the ONLY manual
# pre-script step), and slices each labeled word interval into its own small WAV
# + a blank per-word 6-tier TextGrid (word tier pre-filled). Downstream the
# annotation helper (01) walks these small per-word files for the rep -> segment
# -> landmark cascade, which is far easier than zooming around a 27 s session.
#
# INPUT
#   Session WAV       data/raw/{speaker}.wav            (read-only)
#   Session TextGrid  data/session_textgrids/{speaker}.TextGrid  (word tier only)
#
# OUTPUT  (data/words/{speaker}/)
#   {NN}_{safe_word}.wav        zero-based-time slice (+/- padding)
#   {NN}_{safe_word}.TextGrid   6-tier, tier 1 (word) pre-filled with orthography
#   words_manifest.csv          index,filename,word_label,src_start_s,src_end_s,slice_dur_s
#
# Per-word TextGrid tiers (identical to the rest of the pipeline):
#   1 word(int)  2 rep(int)  3 segment(int)  4 vmid(int)
#   5 landmarks(pt)  6 metadata(pt)
# Tier 1 holds one interval spanning the whole slice, labeled with the word.
#
# IDEMPOTENT: never overwrites an existing per-word TextGrid (annotation is
# precious); (re)writes a WAV only if absent. Manifest is rewritten every run.

form: "Slice session into per-word files"
    comment: "Cut one long recording into one small file per word. Run this once per session."
    comment: "Folders are found automatically from where this script lives; just set the speaker."
    word: "Speaker id", "S1"
    comment: "Word tier = the tier number in the session TextGrid that has the word labels."
    natural: "Word tier", "1"
    comment: "Slice padding = extra milliseconds kept on each side of a word (gives breathing room)."
    positive: "Slice padding (ms)", "50"
endform

pad = slice_padding / 1000
all_tiers$ = "word rep segment vmid landmarks metadata"
point_tiers$ = "landmarks metadata"

# --- Locate the repo from this script's folder (praat/ -> repo root) ---
# defaultDirectory$ is the folder of the running script; the data/ tree sits one
# level up. All paths below are derived from this, so the repo can live anywhere.
repo$ = defaultDirectory$ + "/.."
if not folderExists (repo$ + "/data")
    exitScript: "Can't find the repo's data/ folder from this script's location.", newline$,
        ... "Script folder: ", defaultDirectory$, newline$,
        ... "Open this script from the repo's praat/ folder (Praat -> Open Praat script...) and Run."
endif
session_wav$ = repo$ + "/data/raw/" + speaker_id$ + ".wav"
session_textgrid$ = repo$ + "/data/session_textgrids/" + speaker_id$ + ".TextGrid"
words_base_dir$ = repo$ + "/data/words"

if not fileReadable (session_wav$)
    exitScript: "Session WAV not readable: ", session_wav$
endif
if not fileReadable (session_textgrid$)
    exitScript: "Session TextGrid not readable: ", session_textgrid$
endif

out_dir$ = words_base_dir$ + "/" + speaker_id$
createFolder: out_dir$
manifest$ = out_dir$ + "/words_manifest.csv"
writeFileLine: manifest$, "index,filename,word_label,src_start_s,src_end_s,slice_dur_s"

sound = Read from file: session_wav$
sound_dur = Get total duration
tg = Read from file: session_textgrid$

selectObject: tg
n_tiers = Get number of tiers
if word_tier > n_tiers
    removeObject: sound, tg
    exitScript: "word_tier ", word_tier, " > number of tiers (", n_tiers, ")"
endif
is_int = Is interval tier: word_tier
if not is_int
    removeObject: sound, tg
    exitScript: "Tier ", word_tier, " is not an interval tier."
endif

n_int = Get number of intervals: word_tier
appendInfoLine: "=== slice_words ==="
appendInfoLine: "Session: ", session_wav$, "  (", fixed$ (sound_dur, 3), " s)"

word_idx = 0
n_sliced = 0
n_skipped = 0

for i to n_int
    selectObject: tg
    label$ = Get label of interval: word_tier, i
    if label$ <> ""
        word_idx = word_idx + 1
        w_start = Get starting point: word_tier, i
        w_end = Get end point: word_tier, i

        # padded slice bounds, clamped to the session
        s_start = w_start - pad
        s_end = w_end + pad
        if s_start < 0
            s_start = 0
        endif
        if s_end > sound_dur
            s_end = sound_dur
        endif
        slice_dur = s_end - s_start

        # safe filename stem: NN_safeword
        @sanitize: label$
        safe$ = sanitize.result$
        idx$ = "00" + string$ (word_idx)
        idx$ = right$ (idx$, 2)
        stem$ = idx$ + "_" + safe$
        wav_path$ = out_dir$ + "/" + stem$ + ".wav"
        tg_path$ = out_dir$ + "/" + stem$ + ".TextGrid"

        # manifest row (always)
        appendFileLine: manifest$, idx$, ",", stem$, ",", label$, ",",
            ... fixed$ (s_start, 6), ",", fixed$ (s_end, 6), ",", fixed$ (slice_dur, 6)

        if fileReadable (tg_path$)
            appendInfoLine: "SKIP (TextGrid exists): ", stem$
            n_skipped = n_skipped + 1
        else
            # extract + save WAV (zero-based time) if absent
            if not fileReadable (wav_path$)
                selectObject: sound
                part = Extract part: s_start, s_end, "rectangular", 1, "no"
                Save as WAV file: wav_path$
                removeObject: part
            endif
            # build per-word TextGrid sized to the slice, word tier pre-filled
            slice = Read from file: wav_path$
            wtg = To TextGrid: all_tiers$, point_tiers$
            Set interval text: word_tier, 1, label$
            Save as text file: tg_path$
            removeObject: slice, wtg
            appendInfoLine: "SLICED: ", stem$, "  '", label$, "'  [",
                ... fixed$ (s_start, 3), "-", fixed$ (s_end, 3), "]"
            n_sliced = n_sliced + 1
        endif
    endif
endfor

removeObject: sound, tg

appendInfoLine: "=== done ==="
appendInfoLine: "Words found: ", word_idx
appendInfoLine: "Sliced: ", n_sliced, "   Skipped (existing): ", n_skipped
appendInfoLine: "Output: ", out_dir$

# ============================================================
procedure sanitize: .s$
    .result$ = replace_regex$ (.s$, "[^A-Za-z0-9]", "_", 0)
    .result$ = replace_regex$ (.result$, "_+", "_", 0)
    .result$ = replace_regex$ (.result$, "^_|_$", "", 0)
    if .result$ = ""
        .result$ = "w"
    endif
endproc
