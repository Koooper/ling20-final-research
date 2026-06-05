# 02_extract_measurements.praat
#
# Frozen measurement-extraction script for the Lakota obstruents pipeline.
# Reads the WAV + annotated 6-tier per-word TextGrid produced by the helper, and
# emits one CSV row per labeled target segment with the acoustic battery.
# Computes whatever each segment's committed landmarks allow (measure-by-
# landmark-availability, NOT by declared sound type) so nothing is silently
# dropped because of a mislabeled type. sound_type is emitted for filtering.
#
# DETERMINISTIC: same WAV + TextGrid + these settings => identical numbers.
#
# WINDOWS (derived from committed landmarks on tier 5 / vmid interval on tier 4)
#   W_clo   t_clo   -> t_burst    closure (when t_clo present)
#   W_noise t_burst -> t_voi      release+aspiration (aspirated) / frication
#                                 (affricate) / silent gap (ejective)
#   W_burst t_burst -> t_burst+20ms (capped at t_voi)  burst-peak intensity window
#   W_vow   t_voi   -> t_vend     following vowel
#   W_von   t_voi   -> t_voi+VON  vowel-onset window (capped at 50% of vowel)
#   vmid    tier 4 interval       vowel steady state (midpoint formants)
#
# PHONATION WINDOWS:  H1-H2 + HNR over W_von (onset);  jitter/shimmer over W_vow.
# SPECTRAL MOMENTS:   FFT (To Spectrum), power = 2, Hamming-tapered extract.
# noise_* serves Q2 (aspiration/frication COG) and Q4 (silent-gap intensity) both.
# noise duration == VOT (t_voi - t_burst), so it is not emitted separately.
#
# STATUS: accepted (ok:* marker) | skipped | garbage | partial (marks, no ok) | unmarked

form: "Extract measurements (Lakota obstruents)"
    comment: "Folders are found automatically from where this script lives; just set the speaker."
    word: "Speaker id", "S1"
    natural: "Word tier", "1"
    natural: "Rep tier", "2"
    natural: "Segment tier", "3"
    natural: "Vmid tier", "4"
    natural: "Landmarks tier", "5"
    natural: "Metadata tier", "6"
    positive: "Formant ceiling (Hz)", "5000"
    natural: "Formant number", "5"
    positive: "Pitch floor (Hz)", "75"
    positive: "Pitch ceiling (Hz)", "300"
    positive: "Intensity min pitch (Hz)", "100"
    real: "Recording floor (dB)", "-60"
    real: "Silent offset (dB)", "5"
    positive: "Von window (ms)", "30"
    positive: "f0 contour step (ms)", "10"
endform

von_sec = von_window / 1000
f0_step_sec = f0_contour_step / 1000
silent_thresh_db = recording_floor + silent_offset

# --- Locate the repo from this script's folder (praat/ -> repo root) ---
# defaultDirectory$ is the folder of the running script; the data/ tree sits one
# level up, so the word + output folders are derived and the repo can live anywhere.
repo$ = defaultDirectory$ + "/.."
if not folderExists (repo$ + "/data")
    exitScript: "Can't find the repo's data/ folder from this script's location.", newline$,
        ... "Script folder: ", defaultDirectory$, newline$,
        ... "Open this script from the repo's praat/ folder (Praat -> Open Praat script...) and Run."
endif
words_directory$ = repo$ + "/data/words/" + speaker_id$
output_directory$ = repo$ + "/data/derived/extraction"

if not folderExists (words_directory$)
    exitScript: "Words directory does not exist: ", words_directory$, newline$,
        ... "Run 00_slice_words.praat for speaker ", speaker_id$, " first."
endif
createFolder: output_directory$
outpath$ = output_directory$ + "/measurements_" + speaker_id$ + ".csv"

# --- Header (column order MUST match the addnum/addstr sequence below) ---
header$ = "file,token_id,speaker,rep_label,segment_label,sound_type,status,"
    ... + "seg_start_s,seg_end_s,"
    ... + "t_clo_s,t_burst_s,t_voi_s,t_vend_s,t_glot_rel_s,t_pvend_s,"
    ... + "vot_ms,closure_dur_ms,glottal_oral_ms,vowel_dur_ms,"
    ... + "voiced_closure_prop,voiced_closure_onset_ms,"
    ... + "burst_intensity_db,vowel_onset_intensity_db,burst_vowel_ratio_db,noise_intensity_db,noise_is_silent,"
    ... + "noise_cog_hz,noise_sd_hz,noise_skew,noise_kurt,"
    ... + "sc_f1_onset_hz,sc_f2_onset_hz,sc_f3_onset_hz,sc_f1_mid_hz,sc_f2_mid_hz,sc_f3_mid_hz,"
    ... + "f0_onset_hz,h1_h2_db,hnr_db,jitter_local,shimmer_local,"
    ... + "dup_flag,order_flag,f0_contour_hz"
writeFileLine: outpath$, header$

appendInfoLine: "=== extract_measurements (Lakota obstruents) ==="
appendInfoLine: "Speaker: ", speaker_id$, "  Output: ", outpath$

files$# = fileNames$# (words_directory$ + "/*.wav")
n_files = size (files$#)
if n_files = 0
    exitScript: "No .wav files found in ", words_directory$
endif

rows_written = 0
warn_count = 0

for f to n_files
    wavname$ = files$# [f]
    basename$ = left$ (wavname$, rindex (wavname$, ".") - 1)
    tg_path$ = words_directory$ + "/" + basename$ + ".TextGrid"

    if not fileReadable (tg_path$)
        appendInfoLine: "No TextGrid for ", wavname$, " - skipping"
    else
        sound = Read from file: words_directory$ + "/" + wavname$
        textgrid = Read from file: tg_path$

        # --- Per-file analysis objects (created once) ---
        selectObject: sound
        intensity = noprogress To Intensity: intensity_min_pitch, 0, "yes"
        selectObject: sound
        pitch = noprogress To Pitch: 0, pitch_floor, pitch_ceiling
        selectObject: sound
        formant = noprogress To Formant (burg): 0, formant_number, formant_ceiling, 0.025, 50
        selectObject: sound
        pointprocess = noprogress To PointProcess (periodic, cc): pitch_floor, pitch_ceiling
        selectObject: sound
        harmonicity = noprogress To Harmonicity (cc): 0.01, pitch_floor, 0.1, 4.5

        @process_file
        removeObject: intensity, pitch, formant, pointprocess, harmonicity, sound, textgrid
    endif
endfor

appendInfoLine: "Wrote ", rows_written, " rows to ", outpath$
appendInfoLine: "Warnings (dup/order): ", warn_count

# ============================================================
# FILE DRIVER
# ============================================================
procedure process_file
    selectObject: textgrid
    .n_seg = Get number of intervals: segment_tier
    for .i to .n_seg
        selectObject: textgrid
        .lab$ = Get label of interval: segment_tier, .i
        if .lab$ <> ""
            .s = Get starting point: segment_tier, .i
            .e = Get end point: segment_tier, .i
            @emit_segment: .lab$, .s, .e
        endif
    endfor
endproc

# ============================================================
# ONE SEGMENT -> ONE ROW
# ============================================================
procedure emit_segment: .seg_label$, .seg_start, .seg_end
    # ---- context labels ----
    # word_label (orthography) is intentionally NOT emitted: it is the only
    # non-ASCII field and would force Praat into UTF-16 (Excel-hostile). The
    # readable word lives in token_id (file stem); full orthography is in the
    # manifest + metadata CSV, joined on token_id downstream.
    .mid = (.seg_start + .seg_end) / 2
    @label_at: rep_tier, .mid
    .rep_label$ = label_at.result$

    # ---- sound type + status from metadata tier ----
    @read_status: .seg_start, .seg_end
    .sound_type$ = read_status.type$
    .status$ = read_status.status$

    # ---- landmarks (tier 5); -1 = absent ----
    t_clo = -1
    t_burst = -1
    t_voi = -1
    t_vend = -1
    t_glot = -1
    t_pvend = -1
    c_clo = 0
    c_burst = 0
    c_voi = 0
    c_vend = 0
    c_glot = 0
    c_pvend = 0
    # Closed-right: a landmark (esp. t_vend) often sits exactly on seg_end.
    selectObject: textgrid
    .np = Get number of points: landmarks_tier
    for .p to .np
        .pt = Get time of point: landmarks_tier, .p
        if .pt >= .seg_start and .pt <= .seg_end
            .plab$ = Get label of point: landmarks_tier, .p
            if .plab$ = "t_clo"
                t_clo = .pt
                c_clo = c_clo + 1
            elsif .plab$ = "t_burst"
                t_burst = .pt
                c_burst = c_burst + 1
            elsif .plab$ = "t_voi"
                t_voi = .pt
                c_voi = c_voi + 1
            elsif .plab$ = "t_vend"
                t_vend = .pt
                c_vend = c_vend + 1
            elsif .plab$ = "t_glot_rel"
                t_glot = .pt
                c_glot = c_glot + 1
            elsif .plab$ = "t_pvend"
                t_pvend = .pt
                c_pvend = c_pvend + 1
            endif
        endif
    endfor

    # ---- vmid interval ----
    @find_interval: vmid_tier, .seg_start, .seg_end
    vmid_start = find_interval.start
    vmid_end = find_interval.end

    # ---- duplicate / order flags ----
    .dup = 0
    if c_clo>1 or c_burst>1 or c_voi>1 or c_vend>1 or c_glot>1 or c_pvend>1
        .dup = 1
        warn_count = warn_count + 1
        appendInfoLine: "DUP: ", basename$, " seg '", .seg_label$, "'"
    endif
    .order = 0
    if t_clo>=0 and t_burst>=0 and t_clo >= t_burst
        .order = 1
    endif
    if t_voi>=0 and t_vend>=0 and t_voi >= t_vend
        .order = 1
    endif
    if .order = 1
        warn_count = warn_count + 1
        appendInfoLine: "ORDER: ", basename$, " seg '", .seg_label$, "'"
    endif

    # ---- vowel-onset window end (cap at 50% of vowel) ----
    if t_voi >= 0
        von_end = t_voi + von_sec
        if t_vend >= 0
            .half = t_voi + 0.5 * (t_vend - t_voi)
            if .half < von_end
                von_end = .half
            endif
        endif
    else
        von_end = undefined
    endif

    # ================= TEMPORAL =================
    vot_ms = undefined
    if t_burst>=0 and t_voi>=0
        vot_ms = (t_voi - t_burst) * 1000
    endif
    closure_dur_ms = undefined
    if t_clo>=0 and t_burst>=0
        closure_dur_ms = (t_burst - t_clo) * 1000
    endif
    glottal_oral_ms = undefined
    if t_glot>=0 and t_burst>=0
        glottal_oral_ms = (t_burst - t_glot) * 1000
    endif
    vowel_dur_ms = undefined
    if t_voi>=0 and t_vend>=0
        vowel_dur_ms = (t_vend - t_voi) * 1000
    endif

    # ================= VOICED CLOSURE =================
    voiced_closure_prop = undefined
    voiced_closure_onset_ms = undefined
    if t_clo>=0 and t_burst>=0 and t_burst > t_clo
        selectObject: pitch
        .nf = Get number of frames
        .tot = 0
        .vcd = 0
        .first = undefined
        for .fr to .nf
            .ft = Get time from frame number: .fr
            if .ft >= t_clo and .ft < t_burst
                .tot = .tot + 1
                .val = Get value in frame: .fr, "Hertz"
                if .val <> undefined
                    .vcd = .vcd + 1
                    if .first = undefined
                        .first = .ft
                    endif
                endif
            endif
        endfor
        if .tot > 0
            voiced_closure_prop = .vcd / .tot
        endif
        if .first <> undefined
            voiced_closure_onset_ms = (.first - t_clo) * 1000
        endif
    endif

    # ================= INTENSITY =================
    # Burst peak over a short fixed window after release (no t_burst_end now).
    burst_intensity_db = undefined
    if t_burst>=0
        .b_hi = t_burst + 0.02
        if t_voi>=0 and t_voi < .b_hi
            .b_hi = t_voi
        endif
        if .b_hi > t_burst
            selectObject: intensity
            burst_intensity_db = Get maximum: t_burst, .b_hi, "Parabolic"
        endif
    endif
    vowel_onset_intensity_db = undefined
    if t_voi>=0 and von_end <> undefined and von_end > t_voi
        selectObject: intensity
        vowel_onset_intensity_db = Get mean: t_voi, von_end, "energy"
    endif
    burst_vowel_ratio_db = undefined
    if burst_intensity_db <> undefined and vowel_onset_intensity_db <> undefined
        burst_vowel_ratio_db = burst_intensity_db - vowel_onset_intensity_db
    endif
    # noise window = t_burst -> t_voi (release+aspiration / frication / silent gap)
    noise_intensity_db = undefined
    if t_burst>=0 and t_voi>=0 and t_voi > t_burst
        selectObject: intensity
        noise_intensity_db = Get mean: t_burst, t_voi, "energy"
    endif
    noise_is_silent = undefined
    if noise_intensity_db <> undefined
        if noise_intensity_db < silent_thresh_db
            noise_is_silent = 1
        else
            noise_is_silent = 0
        endif
    endif

    # ================= SPECTRAL MOMENTS =================
    # Single noise window t_burst -> t_voi: aspiration COG (Q2) for aspirated
    # stops, frication COG for affricates, near-flat for ejective silent gaps.
    @spectral_moments: t_burst, t_voi
    noise_cog = spectral_moments.cog
    noise_sd = spectral_moments.sd
    noise_skew = spectral_moments.skew
    noise_kurt = spectral_moments.kurt

    # ================= FORMANTS (single-ceiling, co-compat) =================
    # These are the SINGLE-CEILING formants, emitted under sc_* names. FastTrack's
    # multi-ceiling winner formants are the CANONICAL f1_onset_hz/... and come from
    # the separate 02b_formants pass (joined by token_id in Python). Kept here for the
    # single-vs-FastTrack methods comparison.
    f1_onset = undefined
    f2_onset = undefined
    f3_onset = undefined
    if t_voi>=0 and von_end <> undefined and von_end > t_voi
        selectObject: formant
        f1_onset = Get mean: 1, t_voi, von_end, "hertz"
        f2_onset = Get mean: 2, t_voi, von_end, "hertz"
        f3_onset = Get mean: 3, t_voi, von_end, "hertz"
    endif
    f1_mid = undefined
    f2_mid = undefined
    f3_mid = undefined
    if vmid_start>=0 and vmid_end>=0
        .vc = (vmid_start + vmid_end) / 2
        selectObject: formant
        f1_mid = Get value at time: 1, .vc, "hertz", "linear"
        f2_mid = Get value at time: 2, .vc, "hertz", "linear"
        f3_mid = Get value at time: 3, .vc, "hertz", "linear"
    endif

    # ================= F0 =================
    f0_onset = undefined
    if t_voi>=0
        selectObject: pitch
        f0_onset = Get value at time: t_voi + 0.015, "Hertz", "linear"
    endif
    @f0_contour_str: t_voi, t_vend
    f0_contour$ = f0_contour_str.result$

    # ================= H1-H2 (uncorrected) =================
    h1_h2 = undefined
    if t_voi>=0 and von_end <> undefined and von_end - t_voi > 0.005
        selectObject: pitch
        .f0v = Get value at time: t_voi + 0.015, "Hertz", "linear"
        if .f0v <> undefined
            selectObject: sound
            .von = Extract part: t_voi, von_end, "Hamming", 1, "no"
            .spec = To Spectrum: "yes"
            .ltas = To Ltas (1-to-1)
            .h1 = Get maximum: 0.8 * .f0v, 1.2 * .f0v, "none"
            .h2 = Get maximum: 1.8 * .f0v, 2.2 * .f0v, "none"
            if .h1 <> undefined and .h2 <> undefined
                h1_h2 = .h1 - .h2
            endif
            removeObject: .von, .spec, .ltas
        endif
    endif

    # ================= HNR (W_von) =================
    hnr_db = undefined
    if t_voi>=0 and von_end <> undefined and von_end > t_voi
        selectObject: harmonicity
        hnr_db = Get mean: t_voi, von_end
    endif

    # ================= JITTER / SHIMMER (W_vow) =================
    jitter_local = undefined
    shimmer_local = undefined
    if t_voi>=0 and t_vend>=0 and t_vend > t_voi
        selectObject: pointprocess
        jitter_local = Get jitter (local): t_voi, t_vend, 0.0001, 0.02, 1.3
        selectObject: sound
        plusObject: pointprocess
        shimmer_local = Get shimmer (local): t_voi, t_vend, 0.0001, 0.02, 1.3, 1.6
    endif

    # ================= BUILD ROW =================
    # Join key: speaker_filestem_rep_segment. The file stem (e.g. 01_cake) is
    # already ASCII-safe and unique within the speaker (NN index), so no
    # transliteration needed; raw orthography stays in word_label.
    .token_id$ = speaker_id$ + "_" + basename$ + "_" + .rep_label$ + "_" + .seg_label$
    row$ = ""
    @addstr: basename$
    @addstr: .token_id$
    @addstr: speaker_id$
    @addstr: .rep_label$
    @addstr: .seg_label$
    @addstr: .sound_type$
    @addstr: .status$
    @addnum: .seg_start, 6
    @addnum: .seg_end, 6
    @addsec: t_clo
    @addsec: t_burst
    @addsec: t_voi
    @addsec: t_vend
    @addsec: t_glot
    @addsec: t_pvend
    @addnum: vot_ms, 2
    @addnum: closure_dur_ms, 2
    @addnum: glottal_oral_ms, 2
    @addnum: vowel_dur_ms, 2
    @addnum: voiced_closure_prop, 4
    @addnum: voiced_closure_onset_ms, 2
    @addnum: burst_intensity_db, 2
    @addnum: vowel_onset_intensity_db, 2
    @addnum: burst_vowel_ratio_db, 2
    @addnum: noise_intensity_db, 2
    @addnum: noise_is_silent, 0
    @addnum: noise_cog, 1
    @addnum: noise_sd, 1
    @addnum: noise_skew, 3
    @addnum: noise_kurt, 3
    @addnum: f1_onset, 1
    @addnum: f2_onset, 1
    @addnum: f3_onset, 1
    @addnum: f1_mid, 1
    @addnum: f2_mid, 1
    @addnum: f3_mid, 1
    @addnum: f0_onset, 2
    @addnum: h1_h2, 2
    @addnum: hnr_db, 2
    @addnum: jitter_local, 5
    @addnum: shimmer_local, 5
    @addnum: .dup, 0
    @addnum: .order, 0
    @addstr: f0_contour$

    appendFileLine: outpath$, row$
    rows_written = rows_written + 1
endproc

# ============================================================
# MEASUREMENT HELPERS
# ============================================================
# FFT spectral moments over [.lo,.hi]; sets .cog/.sd/.skew/.kurt (undefined if invalid).
procedure spectral_moments: .lo, .hi
    .cog = undefined
    .sd = undefined
    .skew = undefined
    .kurt = undefined
    if .lo >= 0 and .hi >= 0 and .hi - .lo > 0.001
        selectObject: sound
        .part = Extract part: .lo, .hi, "Hamming", 1, "no"
        .spec = To Spectrum: "yes"
        .cog = Get centre of gravity: 2
        .sd = Get standard deviation: 2
        .skew = Get skewness: 2
        .kurt = Get kurtosis: 2
        removeObject: .part, .spec
    endif
endproc

# Semicolon-joined f0 samples every f0_step over [.lo,.hi]; "NA" for unvoiced.
procedure f0_contour_str: .lo, .hi
    .result$ = ""
    if .lo >= 0 and .hi >= 0 and .hi > .lo
        selectObject: pitch
        .t = .lo
        while .t <= .hi
            .v = Get value at time: .t, "Hertz", "linear"
            if .v = undefined
                .s$ = "NA"
            else
                .s$ = fixed$ (.v, 1)
            endif
            if .result$ = ""
                .result$ = .s$
            else
                .result$ = .result$ + ";" + .s$
            endif
            .t = .t + f0_step_sec
        endwhile
    else
        .result$ = "NA"
    endif
endproc

# ============================================================
# TEXTGRID READ HELPERS
# ============================================================
procedure label_at: .tier, .t
    selectObject: textgrid
    .result$ = ""
    .iv = Get interval at time: .tier, .t
    if .iv >= 1
        .result$ = Get label of interval: .tier, .iv
    endif
endproc

# Find a labeled interval on .tier whose midpoint lies in [.lo,.hi); start/end = -1 if none.
procedure find_interval: .tier, .lo, .hi
    selectObject: textgrid
    .start = -1
    .end = -1
    .n = Get number of intervals: .tier
    for .i to .n
        .lab$ = Get label of interval: .tier, .i
        if .lab$ <> ""
            .s = Get starting point: .tier, .i
            .e = Get end point: .tier, .i
            .m = (.s + .e) / 2
            if .m >= .lo and .m < .hi
                .start = .s
                .end = .e
            endif
        endif
    endfor
endproc

# Read ok:* / skip / garbage on metadata tier; sets .type$ and .status$.
procedure read_status: .lo, .hi
    selectObject: textgrid
    .type$ = ""
    .skip = 0
    .garbage = 0
    .accepted = 0
    .n = Get number of points: metadata_tier
    for .p to .n
        .pt = Get time of point: metadata_tier, .p
        if .pt >= .lo and .pt <= .hi
            .plab$ = Get label of point: metadata_tier, .p
            if .plab$ = "skip"
                .skip = 1
            elsif .plab$ = "garbage"
                .garbage = 1
            elsif left$ (.plab$, 3) = "ok:"
                .accepted = 1
                .type$ = replace$ (.plab$, "ok:", "", 1)
            elsif .plab$ = "ok"
                .accepted = 1
            endif
        endif
    endfor
    if .garbage = 1
        .status$ = "garbage"
    elsif .skip = 1
        .status$ = "skipped"
    elsif .accepted = 1
        .status$ = "accepted"
    else
        .status$ = "partial"
    endif
endproc

# ============================================================
# ROW-BUILDING HELPERS (append to global row$)
# ============================================================
procedure addnum: .v, .dec
    if .v = undefined
        .s$ = "NA"
    else
        .s$ = fixed$ (.v, .dec)
    endif
    if row$ = ""
        row$ = .s$
    else
        row$ = row$ + "," + .s$
    endif
endproc

# Landmark time in seconds; -1 sentinel -> NA.
procedure addsec: .v
    if .v < 0
        .s$ = "NA"
    else
        .s$ = fixed$ (.v, 6)
    endif
    if row$ = ""
        row$ = .s$
    else
        row$ = row$ + "," + .s$
    endif
endproc

procedure addstr: .v$
    .clean$ = replace_regex$ (.v$, "[,\n\r\t]+", " ", 0)
    if row$ = ""
        row$ = .clean$
    else
        row$ = row$ + "," + .clean$
    endif
endproc
