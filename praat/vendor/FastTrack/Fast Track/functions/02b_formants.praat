# 02b_formants.praat  --  REPO-AUTHORED (Lakota obstruents pipeline), not upstream FastTrack.
#
# Canonical formant pass. Runs the vendored FastTrack multi-ceiling winner-selection per
# target vowel and writes formants_{speaker}.csv (token_id-keyed), which the Python pipeline
# joins onto the frame by token_id (load_formants.merge_formants). These are the CANONICAL
# F1-F3; 02's single-ceiling formants ride alongside as sc_* for the methods comparison.
#
# WHY THIS LIVES INSIDE Fast Track/functions/: Praat resolves `include` relative to the MAIN
# script, and FastTrack's nested includes assume the caller sits here. So this one repo file
# is vendored alongside upstream (everything else under praat/vendor/FastTrack/ is upstream).
#
# token_id MUST match 02 exactly: {speaker}_{filestem}_{rep}_{segment}. If 02 changes its
# token_id construction, change it here too or the join silently leaves formants NA.
#
# DETERMINISTIC: same WAV + TextGrid + these settings => identical numbers.
#
# Two modes:
#   extract : headless (command line ok) - every accepted target -> formants_{speaker}.csv
#   images  : run from the Praat GUI - render FastTrack comparison images for ONLY the tokens
#             in data/derived/validation/handcheck_tokens_{speaker}.csv (the 12% subset).

form: "FastTrack formants (Lakota obstruents)"
    comment: "Defaults should mirror config/pipeline_config.yaml (speakers.* + analysis.fasttrack)."
    word: "Speaker id", "S1"
    optionmenu: "Mode", 1
        option: "extract"
        option: "images"
    natural: "Rep tier", "2"
    natural: "Segment tier", "3"
    natural: "Vmid tier", "4"
    natural: "Landmarks tier", "5"
    natural: "Metadata tier", "6"
    positive: "FastTrack low (Hz)", "4500"
    positive: "FastTrack high (Hz)", "6500"
    natural: "Steps", "16"
    natural: "Coefficients", "5"
    natural: "Number of formants", "4"
    positive: "Buffer (ms)", "50"
    positive: "Von window (ms)", "30"
    positive: "Max plot freq (Hz)", "5500"
endform

von_sec = von_window / 1000
buffer_sec = buffer / 1000

# --- Locate the repo: this script sits at praat/vendor/FastTrack/Fast Track/functions/ ---
repo$ = defaultDirectory$ + "/../../../../.."
if not folderExists (repo$ + "/data")
    exitScript: "Can't find the repo's data/ folder from this script's location.", newline$,
        ... "Script folder: ", defaultDirectory$, newline$,
        ... "This script must stay inside praat/vendor/FastTrack/Fast Track/functions/."
endif
words_directory$ = repo$ + "/data/words/" + speaker_id$
output_directory$ = repo$ + "/data/derived/extraction"
if not folderExists (words_directory$)
    exitScript: "Words directory does not exist: ", words_directory$
endif
createFolder: output_directory$
outpath$ = output_directory$ + "/formants_" + speaker_id$ + ".csv"

# --- Load FastTrack (its nested includes resolve because we are in functions/) ---
include utils/trackAutoselectProcedure.praat

# --- FastTrack globals findError/trackAutoselect read (skip @getSettings: it can exit on an
#     unset working folder; we set everything explicitly to stay self-contained). ---
time_step = 0.002
folder$ = output_directory$
enable_F1_frequency_heuristic = 1
maximum_F1_frequency_value = 1200
enable_F1_bandwidth_heuristic = 0
maximum_F1_bandwidth_value = 500
enable_F2_bandwidth_heuristic = 0
maximum_F2_bandwidth_value = 600
enable_F3_bandwidth_heuristic = 0
maximum_F3_bandwidth_value = 900
enable_F4_frequency_heuristic = 1
minimum_F4_frequency_value = 2900
enable_rhotic_heuristic = 1
enable_F3F4_proximity_heuristic = 1

# --- images mode: load the hand-check token list + ensure the output dir exists ---
images_dir$ = repo$ + "/figures/formant_winners/" + speaker_id$
if mode$ = "images"
    hc_path$ = repo$ + "/data/derived/validation/handcheck_tokens_" + speaker_id$ + ".csv"
    if not fileReadable (hc_path$)
        exitScript: "No hand-check list: ", hc_path$, newline$,
            ... "Run the Python pipeline first to emit handcheck_tokens_", speaker_id$, ".csv."
    endif
    hc_table = Read Table from comma-separated file: hc_path$
    createFolder: images_dir$
    createFolder: images_dir$ + "/images_comparison"
    folder$ = images_dir$
endif

# --- extract mode: build the header (coeff columns scale with Coefficients) ---
if mode$ = "extract"
    header$ = "token_id,f1_onset_hz,f2_onset_hz,f3_onset_hz,f1_mid_hz,f2_mid_hz,f3_mid_hz,"
        ... + "f1_p20_hz,f2_p20_hz,f3_p20_hz,f1_p50_hz,f2_p50_hz,f3_p50_hz,"
        ... + "f1_p80_hz,f2_p80_hz,f3_p80_hz,"
    for fnum to 3
        for c from 0 to coefficients
            header$ = header$ + "f" + string$(fnum) + "_c" + string$(c) + ","
        endfor
    endfor
    header$ = header$ + "ft_ceiling_hz,ft_minerror,ft_ceiling_at_bound"
    writeFileLine: outpath$, header$
endif

appendInfoLine: "=== 02b FastTrack formants (", mode$, ") ==="
appendInfoLine: "Speaker: ", speaker_id$, "  range: ", fastTrack_low, "-", fastTrack_high, " Hz"

files$# = fileNames$# (words_directory$ + "/*.wav")
n_files = size (files$#)
if n_files = 0
    exitScript: "No .wav files found in ", words_directory$
endif

rows_written = 0
images_made = 0

for f to n_files
    wavname$ = files$# [f]
    basename$ = left$ (wavname$, rindex (wavname$, ".") - 1)
    tg_path$ = words_directory$ + "/" + basename$ + ".TextGrid"
    if fileReadable (tg_path$)
        sound = Read from file: words_directory$ + "/" + wavname$
        snd_dur = Get total duration
        textgrid = Read from file: tg_path$
        @process_file
        removeObject: sound, textgrid
    endif
endfor

if mode$ = "extract"
    appendInfoLine: "Wrote ", rows_written, " formant rows to ", outpath$
else
    removeObject: hc_table
    appendInfoLine: "Saved ", images_made, " comparison images to ", images_dir$
endif

# ============================================================
# FILE DRIVER  (mirror of 02: walk labeled segment intervals)
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
# ONE SEGMENT -> ONE FORMANT ROW (accepted + has t_voi & t_vend)
# ============================================================
procedure emit_segment: .seg_label$, .seg_start, .seg_end
    .mid = (.seg_start + .seg_end) / 2
    @label_at: rep_tier, .mid
    .rep_label$ = label_at.result$
    @read_status: .seg_start, .seg_end
    .status$ = read_status.status$

    # landmarks (tier 5): only t_voi / t_vend needed here
    t_voi = -1
    t_vend = -1
    selectObject: textgrid
    .np = Get number of points: landmarks_tier
    for .p to .np
        .pt = Get time of point: landmarks_tier, .p
        if .pt >= .seg_start and .pt <= .seg_end
            .plab$ = Get label of point: landmarks_tier, .p
            if .plab$ = "t_voi"
                t_voi = .pt
            elsif .plab$ = "t_vend"
                t_vend = .pt
            endif
        endif
    endfor

    # only accepted targets with a measurable following vowel
    if .status$ <> "accepted" or t_voi < 0 or t_vend < 0 or t_vend <= t_voi
        goto SKIP
    endif

    .token_id$ = speaker_id$ + "_" + basename$ + "_" + .rep_label$ + "_" + .seg_label$

    # images mode: only render tokens in the hand-check subset
    if mode$ = "images"
        @in_handcheck: .token_id$
        if not in_handcheck.found
            goto SKIP
        endif
    endif

    # vmid interval center (for mid formants)
    @find_interval: vmid_tier, .seg_start, .seg_end
    .vmid_start = find_interval.start
    .vmid_end = find_interval.end

    # onset window end (cap at 50% of vowel) - identical to 02 so sc_ and canonical align
    .von_end = t_voi + von_sec
    .half = t_voi + 0.5 * (t_vend - t_voi)
    if .half < .von_end
        .von_end = .half
    endif

    # extract the vowel + real-audio buffer (dodges FastTrack's 25ms edge dead-zone), keep times
    .lo = t_voi - buffer_sec
    if .lo < 0
        .lo = 0
    endif
    .hi = t_vend + buffer_sec
    if .hi > snd_dur
        .hi = snd_dur
    endif
    selectObject: sound
    .part = Extract part: .lo, .hi, "rectangular", 1, "yes"
    Rename: "fttoken"

    if mode$ = "images"
        # image=2 draws the comparison grid into the Picture window (GUI only). Re-save it under
        # the token name (the proc's own save uses the fixed part name and would be overwritten).
        @trackAutoselect: .part, folder$, fastTrack_low, fastTrack_high, steps, coefficients,
            ... number_of_formants, "burg", 2, .part, 0, max_plot_freq, 0, 0, 0
        nocheck Save as 300-dpi PNG file: images_dir$ + "/images_comparison/" + .token_id$ + "_comparison.png"
        nocheck removeObject: .part
        images_made = images_made + 1
        goto SKIP
    endif

    # extract mode: get the winning Formant (renamed to the part's basename) and sample it
    @trackAutoselect: .part, folder$, fastTrack_low, fastTrack_high, steps, coefficients,
        ... number_of_formants, "burg", 0, .part, 0, max_plot_freq, 2, 0, 0
    selectObject: "Formant fttoken"
    .winner = selected ("Formant")

    .f1on = Get mean: 1, t_voi, .von_end, "hertz"
    .f2on = Get mean: 2, t_voi, .von_end, "hertz"
    .f3on = Get mean: 3, t_voi, .von_end, "hertz"
    .f1mid = undefined
    .f2mid = undefined
    .f3mid = undefined
    if .vmid_start >= 0 and .vmid_end >= 0
        .vc = (.vmid_start + .vmid_end) / 2
        .f1mid = Get value at time: 1, .vc, "hertz", "linear"
        .f2mid = Get value at time: 2, .vc, "hertz", "linear"
        .f3mid = Get value at time: 3, .vc, "hertz", "linear"
    endif
    .t20 = t_voi + 0.2 * (t_vend - t_voi)
    .t50 = t_voi + 0.5 * (t_vend - t_voi)
    .t80 = t_voi + 0.8 * (t_vend - t_voi)
    .f1p20 = Get value at time: 1, .t20, "hertz", "linear"
    .f2p20 = Get value at time: 2, .t20, "hertz", "linear"
    .f3p20 = Get value at time: 3, .t20, "hertz", "linear"
    .f1p50 = Get value at time: 1, .t50, "hertz", "linear"
    .f2p50 = Get value at time: 2, .t50, "hertz", "linear"
    .f3p50 = Get value at time: 3, .t50, "hertz", "linear"
    .f1p80 = Get value at time: 1, .t80, "hertz", "linear"
    .f2p80 = Get value at time: 2, .t80, "hertz", "linear"
    .f3p80 = Get value at time: 3, .t80, "hertz", "linear"

    .ceiling = trackAutoselect.cutoff
    .minerror = trackAutoselect.minerror
    .bound = 0
    if .ceiling = round(fastTrack_low) or .ceiling = round(fastTrack_high)
        .bound = 1
    endif

    # ---- build row ----
    row$ = .token_id$
    @addnum: .f1on, 1
    @addnum: .f2on, 1
    @addnum: .f3on, 1
    @addnum: .f1mid, 1
    @addnum: .f2mid, 1
    @addnum: .f3mid, 1
    @addnum: .f1p20, 1
    @addnum: .f2p20, 1
    @addnum: .f3p20, 1
    @addnum: .f1p50, 1
    @addnum: .f2p50, 1
    @addnum: .f3p50, 1
    @addnum: .f1p80, 1
    @addnum: .f2p80, 1
    @addnum: .f3p80, 1
    for .ci to coefficients + 1
        @addnum: trackAutoselect.f1coeffs#[.ci], 2
    endfor
    for .ci to coefficients + 1
        @addnum: trackAutoselect.f2coeffs#[.ci], 2
    endfor
    for .ci to coefficients + 1
        @addnum: trackAutoselect.f3coeffs#[.ci], 2
    endfor
    @addnum: .ceiling, 0
    @addnum: .minerror, 1
    @addnum: .bound, 0

    appendFileLine: outpath$, row$
    rows_written = rows_written + 1
    removeObject: .winner, .part

    label SKIP
endproc

# ============================================================
# HELPERS (copied from 02 so the two stay in lockstep)
# ============================================================
procedure label_at: .tier, .t
    selectObject: textgrid
    .result$ = ""
    .iv = Get interval at time: .tier, .t
    if .iv >= 1
        .result$ = Get label of interval: .tier, .iv
    endif
endproc

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

procedure read_status: .lo, .hi
    selectObject: textgrid
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

# membership test against the hand-check Table (images mode)
procedure in_handcheck: .tid$
    selectObject: hc_table
    .found = 0
    .n = Get number of rows
    for .r to .n
        .v$ = Get value: .r, "token_id"
        if .v$ = .tid$
            .found = 1
        endif
    endfor
endproc

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
