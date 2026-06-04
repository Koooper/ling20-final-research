# 01_annotate_helper.praat
#
# Stage B of the Lakota obstruents pipeline. Walks the per-word WAV+TextGrid
# files produced by 00_slice_words and guides annotation in three phases per
# word file:
#   PHASE 1  reps      drag-select each repetition  -> auto-labeled r1, r2, ...
#   PHASE 2  segments  per rep, drag-select target segment(s) -> auto-labeled s1, s2, ...
#   PHASE 3  landmarks per segment, pick sound type + place points/intervals
# The word identity is already on tier 1 (pre-filled by the slicer); the file IS
# the word, so there is no session-wide zooming.
#
# TIERS (per-word file, from 00_slice_words):
#   1 word(int, pre-filled)  2 rep(int)  3 segment(int)  4 vmid(int)
#   5 landmarks(pt)  6 metadata(pt)
#
# POINT LANDMARKS (tier 5):  t_clo t_burst t_voi t_vend t_glot_rel t_pvend
# SOUND TYPES -> prompted landmarks (uniform set; ejectives add t_glot_rel):
#   stop_plain/aspirated     t_clo? t_burst t_voi t_vend
#   stop_ejective            + t_glot_rel
#   affricate_plain/asp/ej   t_clo? t_burst t_voi t_vend  (+ t_glot_rel if ejective)
# All types mark a vmid interval (tier 4). No burst-offset, no fric interval:
# the burst->voicing window captures aspiration and affricate frication alike.
# METADATA (tier 6): ok:{sound_type} | skip | garbage
#
# NOTE: do not manually close the editor mid-session (Praat gives no way to
# detect/reopen it) - use the Exit button. If you do, the script exits cleanly
# and resume recovers (done segments are skipped). Drag the first pause window
# aside once; Praat keeps subsequent pause windows in that spot.
#
# Reps/segments auto-numbered in time order. Drag-select a region in the editor,
# click Mark; Done when finished. RESUME skips phases already populated.
#
# INTERACTIVE: drag-select + cursor reads happen while a pause dialog is open
# (standard Praat annotation-helper pattern). Editor stays open for the whole file.

form: "Annotate per-word files (Lakota obstruents)"
    comment: "Walks your speaker's word files and guides you through marking each one. The"
    comment: "folder is found automatically from where this script lives; just set the speaker."
    comment: "Drag the first popup window aside so it doesn't cover the sound editor."
    comment: "Use the Exit button - don't close the editor."
    word: "Speaker id", "S1"
    boolean: "Resume (skip parts already marked)", 1
    comment: "View padding = extra milliseconds shown around the part you're working on."
    positive: "View padding (ms)", "120"
    natural: "Word tier", "1"
    natural: "Rep tier", "2"
    natural: "Segment tier", "3"
    natural: "Vmid tier", "4"
    natural: "Landmarks tier", "5"
    natural: "Metadata tier", "6"
endform

pad = view_padding / 1000
eps = 0.0005

# --- Locate the repo from this script's folder (praat/ -> repo root) ---
# defaultDirectory$ is the folder of the running script; the data/ tree sits one
# level up, so the word folder is derived and the repo can live anywhere.
repo$ = defaultDirectory$ + "/.."
if not folderExists (repo$ + "/data")
    exitScript: "Can't find the repo's data/ folder from this script's location.", newline$,
        ... "Script folder: ", defaultDirectory$, newline$,
        ... "Open this script from the repo's praat/ folder (Praat -> Open Praat script...) and Run."
endif
words_directory$ = repo$ + "/data/words/" + speaker_id$

if not folderExists (words_directory$)
    exitScript: "Words directory does not exist: ", words_directory$, newline$,
        ... "Run 00_slice_words.praat for speaker ", speaker_id$, " first."
endif

files$# = fileNames$# (words_directory$ + "/*.wav")
n_files = size (files$#)
if n_files = 0
    exitScript: "No .wav files in ", words_directory$
endif

appendInfoLine: "=== annotate_helper (per-word) ==="
appendInfoLine: "Words dir: ", words_directory$, "  (", n_files, " word file(s))"

user_exit = 0

for f to n_files
    if user_exit = 0
        wavname$ = files$# [f]
        basename$ = left$ (wavname$, rindex (wavname$, ".") - 1)
        tg_path$ = words_directory$ + "/" + basename$ + ".TextGrid"
        if not fileReadable (tg_path$)
            appendInfoLine: "No TextGrid for ", wavname$, " - skipping (run 00_slice_words first)"
        else
            sound = Read from file: words_directory$ + "/" + wavname$
            textgrid = Read from file: tg_path$
            appendInfoLine: "--- ", basename$, " ---"
            @process_word_file
            removeObject: sound, textgrid
        endif
    endif
endfor

if user_exit = 1
    appendInfoLine: "Exited early by user request."
else
    appendInfoLine: "Done."
endif

# ============================================================
# WORD-FILE DRIVER (one editor for the whole file, three phases)
# ============================================================
procedure process_word_file
    selectObject: sound
    file_dur = Get total duration

    selectObject: sound
    plusObject: textgrid
    View & Edit
    editor: textgrid
        nocheck Show analyses: "yes", "yes", "yes", "yes", "yes", 10
        nocheck Spectrogram settings: 0, 8000, 0.005, 50
        Zoom: 0, file_dur
    endeditor

    @phase_reps
    if user_exit = 0
        @phase_segments
    endif
    if user_exit = 0
        @phase_landmarks
    endif

    editor: textgrid
        Close
    endeditor
    selectObject: textgrid
    Save as text file: tg_path$
endproc

# ---------- PHASE 1: reps ----------
procedure phase_reps
    @count_labeled: rep_tier, 0, file_dur
    if resume = 1 and count_labeled.result > 0
        appendInfoLine: "  reps already marked (", count_labeled.result, ") - skipping"
    else
        @collect_intervals: rep_tier, 0, file_dur, "r", "repetition",
            ... "Each time the speaker says this word is one repetition. Highlight one whole spoken word."
    endif
endproc

# ---------- PHASE 2: segments per rep ----------
procedure phase_segments
    @read_intervals: rep_tier, 0, file_dur
    .nr = read_intervals.n
    for .k to .nr
        rep_start [.k] = read_intervals.start [.k]
        rep_end [.k] = read_intervals.end [.k]
        rep_label$ [.k] = read_intervals.label$ [.k]
    endfor
    for .k to .nr
        if user_exit = 0
            @count_labeled: segment_tier, rep_start [.k], rep_end [.k]
            if resume = 1 and count_labeled.result > 0
                appendInfoLine: "  rep ", rep_label$ [.k], ": segments exist - skipping"
            else
                @collect_intervals: segment_tier, rep_start [.k], rep_end [.k], "s", "target sound",
                    ... "Highlight the target consonant PLUS the vowel right after it. If this word has more than one target sound, mark each one."
            endif
        endif
    endfor
endproc

# ---------- PHASE 3: landmarks per segment ----------
procedure phase_landmarks
    @read_intervals: segment_tier, 0, file_dur
    .ns = read_intervals.n
    for .k to .ns
        seg_start [.k] = read_intervals.start [.k]
        seg_end [.k] = read_intervals.end [.k]
        seg_label$ [.k] = read_intervals.label$ [.k]
    endfor
    for .k to .ns
        if user_exit = 0
            @has_terminal: metadata_tier, seg_start [.k], seg_end [.k]
            if resume = 1 and has_terminal.result = 1
                appendInfoLine: "  segment ", seg_label$ [.k], ": already done - skipping"
            else
                @process_segment: seg_label$ [.k], seg_start [.k], seg_end [.k]
            endif
        endif
    endfor
endproc

# ============================================================
# GENERIC INTERVAL COLLECTION (reps + segments share this)
# ============================================================
procedure collect_intervals: .tier, .lo, .hi, .prefix$, .what$, .hint$
    .vlo = .lo - pad
    if .vlo < 0
        .vlo = 0
    endif
    editor: textgrid
        Zoom: .vlo, .hi + pad
    endeditor

    .done = 0
    while .done = 0 and user_exit = 0
        beginPause: "Mark the " + .what$ + "s"
            comment: .hint$
            comment: "Click and DRAG in the oscillogram to highlight a region, then click 'Mark'."
            comment: "Repeat for each one. Click 'Done' when they are all marked."
            comment: "('Exit' stops for now; your work so far is saved.)"
        .clicked = endPause: "Exit", "Done", "Mark", 3, 1
        if .clicked = 1
            user_exit = 1
        elsif .clicked = 2
            .done = 1
        else
            editor: textgrid
                .sl = Get start of selection
                .sh = Get end of selection
            endeditor
            if .sh - .sl < eps
                appendInfoLine: "  (no selection - ignored)"
            else
                if .sl < .lo
                    .sl = .lo
                endif
                if .sh > .hi
                    .sh = .hi
                endif
                @set_interval: .tier, .sl, .sh, "tmp"
            endif
        endif
    endwhile

    @renumber: .tier, .lo, .hi, .prefix$
endproc

# Renumber labeled intervals on .tier whose midpoint is in [.lo,.hi] -> prefix1,2,...
procedure renumber: .tier, .lo, .hi, .prefix$
    selectObject: textgrid
    .n = Get number of intervals: .tier
    .k = 0
    for .i to .n
        .lab$ = Get label of interval: .tier, .i
        if .lab$ <> ""
            .s = Get starting point: .tier, .i
            .e = Get end point: .tier, .i
            .m = (.s + .e) / 2
            if .m >= .lo and .m <= .hi
                .k = .k + 1
                Set interval text: .tier, .i, .prefix$ + string$ (.k)
            endif
        endif
    endfor
endproc

# ============================================================
# SEGMENT LANDMARK FLOW (editor already open; just zoom)
# ============================================================
procedure process_segment: .seg_label$, .seg_start, .seg_end
    .mid = (.seg_start + .seg_end) / 2
    @label_at: word_tier, .mid
    .word$ = label_at.result$
    @label_at: rep_tier, .mid
    .rep$ = label_at.result$
    .vlo = .seg_start - pad
    if .vlo < 0
        .vlo = 0
    endif
    .vhi = .seg_end + pad

    .seg_done = 0
    while .seg_done = 0 and user_exit = 0
        @clear_segment: .seg_start, .seg_end
        editor: textgrid
            Zoom: .vlo, .vhi
            Select: .seg_start, .seg_end
            Move cursor to: .seg_start
        endeditor

        beginPause: "Sound " + .seg_label$ + "  in  " + .word$ + "  (repetition " + .rep$ + ")"
            comment: "What kind of sound are you measuring? Pick from the menu:"
            optionMenu: "Sound type", 1
                option: "plain stop"
                option: "aspirated stop"
                option: "ejective stop"
                option: "plain affricate"
                option: "aspirated affricate"
                option: "ejective affricate"
            comment: "Continue = start placing marks. Skip = can't measure this one."
            comment: "Garbage = bad recording. Exit = stop for now (your work so far is saved)."
        .clicked = endPause: "Exit", "Skip", "Garbage", "Continue", 4, 1

        if .clicked = 1
            user_exit = 1
        elsif .clicked = 2
            @insert_meta: .seg_start, "skip"
            @save_tg
            .seg_done = 1
        elsif .clicked = 3
            @insert_meta: .seg_start, "garbage"
            @save_tg
            .seg_done = 1
        else
            @map_sound_type: sound_type
            @place_landmarks: .seg_label$, .seg_start, .seg_end
            if place_landmarks.action = 1
                @insert_meta: .seg_start, "ok:" + map_sound_type.name$
                @save_tg
                .seg_done = 1
            elsif place_landmarks.action = 3
                @clear_segment: .seg_start, .seg_end
                @insert_meta: .seg_start, "skip"
                @save_tg
                .seg_done = 1
            elsif place_landmarks.action = 4
                @clear_segment: .seg_start, .seg_end
                @insert_meta: .seg_start, "garbage"
                @save_tg
                .seg_done = 1
            endif
            # action = 2 (redo): loop
        endif
    endwhile
endproc

# One landmark-placement attempt; sets .action (1 accept, 2 redo, 3 skip, 4 garbage).
# To place a point: click in the waveform/spectrogram to move the cursor, then Mark.
procedure place_landmarks: .label$, .seg_start, .seg_end
    .ctx$ = "sound " + .label$

    beginPause: "Closure start  (t_clo)  —  " + .ctx$
        comment: "Where the consonant's silent CLOSURE begins: the moment the previous"
        comment: "sound ends and the oscillogram goes flat and quiet."
        comment: "Only place if intervocalic."
        comment: "If word initial, just click Skip."
        comment: "Click in the oscillogram to set the cursor, then click 'Mark t_clo'."
    .c = endPause: "Skip", "Mark t_clo", 2, 1
    if .c = 2
        @mark_point_from_cursor: "t_clo"
    endif

    beginPause: "Release / burst  (t_burst)  —  " + .ctx$
        comment: "The RELEASE: the consonant's stop burst"
        comment: "For affricates, use the moment the noise begins."
        comment: "Set the cursor at that spike, then click 'Mark t_burst'."
    .c = endPause: "Skip", "Mark t_burst", 2, 1
    if .c = 2
        @mark_point_from_cursor: "t_burst"
    endif

    if map_sound_type.prompt_glot_rel = 1
        beginPause: "Ejective pop  (t_glot_rel)  —  " + .ctx$
            comment: "EJECTIVES ONLY. Just after the main release there could be a"
            comment: "different burst a moment later. Might be a glottal release??"
            comment: "Set the cursor on that second pop, then 'Mark t_glot_rel'."
            comment: "If you cannot see a separate second pop, click Skip."
        .c = endPause: "Skip", "Mark t_glot_rel", 2, 1
        if .c = 2
            @mark_point_from_cursor: "t_glot_rel"
        endif
    endif

    beginPause: "Voicing start  (t_voi)  —  " + .ctx$
        comment: "Where the following VOWEL's voicing begins: the first pulse of"
        comment: "quasi-periodic wave. Visualized pulses are good here but not conclusive."
        comment: "Use your judgment. Can be placed before closure for prevoicing."
        comment: "Set the cursor there, then click 'Mark t_voi'."
    .c = endPause: "Skip", "Mark t_voi", 2, 1
    if .c = 2
        @mark_point_from_cursor: "t_voi"
    endif

    beginPause: "Vowel end  (t_vend)  —  " + .ctx$
        comment: "Where the following vowel ENDS: Measuring this for locus stuff. Trust."
        comment: "If dipthong or generally weird, just end at the last decent spot."
        comment: "Set the cursor there, then click 'Mark t_vend'."
    .c = endPause: "Skip", "Mark t_vend", 2, 1
    if .c = 2
        @mark_point_from_cursor: "t_vend"
    endif

    beginPause: "Vowel middle  (vmid)  —  " + .ctx$
        comment: "Click and DRAG to highlight the steady MIDDLE of the vowel: "
        comment: "Grab a stable stretch of F1 and F2 after locus movement."
        comment: "Then click 'Mark vmid'. (Used to measure the vowel's quality.)"
    .c = endPause: "Skip", "Mark vmid", 2, 1
    if .c = 2
        @mark_interval_from_selection: vmid_tier, "vmid"
    endif

    beginPause: "Earlier vowel end  (t_pvend)  —  " + .ctx$
        comment: "OPTIONAL and usually skipped. Only if a vowel from the PREVIOUS word"
        comment: "runs right up to this one and its voicing bleeds across the boundary."
        comment: "Probably won't need this?"
        comment: "If so, set the cursor where that earlier vowel ends and Mark. Otherwise Skip."
    .c = endPause: "Skip", "Mark t_pvend", 1, 1
    if .c = 2
        @mark_point_from_cursor: "t_pvend"
    endif

    beginPause: "Done with sound " + .label$ + "?"
        comment: "Check your marks in the editor."
        comment: "Accept = save and go to the next sound."
        comment: "Redo = clear these marks and place them again."
        comment: "Skip = this sound can't be measured (e.g. too unclear)."
        comment: "Garbage = the recording itself is bad (noise, cut off, wrong word)."
    .action = endPause: "Redo", "Skip", "Garbage", "Accept", 4, 1
    if .action = 1
        .action = 2
    elsif .action = 2
        .action = 3
    elsif .action = 3
        .action = 4
    elsif .action = 4
        .action = 1
    endif
endproc

# ============================================================
# SOUND-TYPE MAP
# ============================================================
procedure map_sound_type: .idx
    if .idx = 1
        .name$ = "stop_plain"
        .prompt_glot_rel = 0
    elsif .idx = 2
        .name$ = "stop_aspirated"
        .prompt_glot_rel = 0
    elsif .idx = 3
        .name$ = "stop_ejective"
        .prompt_glot_rel = 1
    elsif .idx = 4
        .name$ = "affricate_plain"
        .prompt_glot_rel = 0
    elsif .idx = 5
        .name$ = "affricate_aspirated"
        .prompt_glot_rel = 0
    else
        .name$ = "affricate_ejective"
        .prompt_glot_rel = 1
    endif
endproc

# ============================================================
# EDITOR -> TEXTGRID HELPERS
# ============================================================
procedure mark_point_from_cursor: .plabel$
    editor: textgrid
        .t = Get cursor
    endeditor
    selectObject: textgrid
    # Collision-safe: remove any existing point at (essentially) this exact time
    # first; Insert point errors on an exact-time collision and would crash.
    .p = Get number of points: landmarks_tier
    while .p >= 1
        .pt = Get time of point: landmarks_tier, .p
        if abs (.pt - .t) < 1e-9
            Remove point: landmarks_tier, .p
        endif
        .p = .p - 1
    endwhile
    Insert point: landmarks_tier, .t, .plabel$
endproc

procedure mark_interval_from_selection: .tier, .ilabel$
    editor: textgrid
        .lo = Get start of selection
        .hi = Get end of selection
    endeditor
    if .hi - .lo < eps
        appendInfoLine: "  (no selection for ", .ilabel$, " - skipped)"
    else
        @set_interval: .tier, .lo, .hi, .ilabel$
    endif
endproc

procedure set_interval: .tier, .lo, .hi, .ilabel$
    selectObject: textgrid
    @clear_interval_in_range: .tier, .lo, .hi
    nocheck Insert boundary: .tier, .lo
    nocheck Insert boundary: .tier, .hi
    .imid = (.lo + .hi) / 2
    .iv = Get interval at time: .tier, .imid
    Set interval text: .tier, .iv, .ilabel$
endproc

procedure insert_meta: .seg_start, .mlabel$
    selectObject: textgrid
    Insert point: metadata_tier, .seg_start + 0.001, .mlabel$
endproc

procedure save_tg
    selectObject: textgrid
    Save as text file: tg_path$
endproc

# ============================================================
# RANGE QUERIES / CLEARING
# ============================================================
procedure count_labeled: .tier, .lo, .hi
    selectObject: textgrid
    .result = 0
    .n = Get number of intervals: .tier
    for .i to .n
        .lab$ = Get label of interval: .tier, .i
        if .lab$ <> ""
            .s = Get starting point: .tier, .i
            .e = Get end point: .tier, .i
            .m = (.s + .e) / 2
            if .m >= .lo and .m <= .hi
                .result = .result + 1
            endif
        endif
    endfor
endproc

procedure read_intervals: .tier, .lo, .hi
    selectObject: textgrid
    .n = 0
    .ni = Get number of intervals: .tier
    for .i to .ni
        .lab$ = Get label of interval: .tier, .i
        if .lab$ <> ""
            .s = Get starting point: .tier, .i
            .e = Get end point: .tier, .i
            .m = (.s + .e) / 2
            if .m >= .lo and .m <= .hi
                .n = .n + 1
                .start [.n] = .s
                .end [.n] = .e
                .label$ [.n] = .lab$
            endif
        endif
    endfor
endproc

procedure has_terminal: .tier, .lo, .hi
    selectObject: textgrid
    .result = 0
    .n = Get number of points: .tier
    for .p to .n
        .pt = Get time of point: .tier, .p
        if .pt >= .lo and .pt <= .hi
            .plab$ = Get label of point: .tier, .p
            if left$ (.plab$, 2) = "ok" or .plab$ = "skip" or .plab$ = "garbage"
                .result = 1
            endif
        endif
    endfor
endproc

procedure label_at: .tier, .t
    selectObject: textgrid
    .result$ = ""
    .iv = Get interval at time: .tier, .t
    if .iv >= 1
        .result$ = Get label of interval: .tier, .iv
    endif
endproc

# Remove all points in [lo,hi] on a point tier (closed-right: t_vend may sit on seg_end).
procedure clear_points_in_range: .tier, .lo, .hi
    selectObject: textgrid
    .p = Get number of points: .tier
    while .p >= 1
        .pt = Get time of point: .tier, .p
        if .pt >= .lo and .pt <= .hi
            Remove point: .tier, .p
        endif
        .p = .p - 1
    endwhile
endproc

# Remove interval boundaries strictly inside (lo,hi), merging intervals back.
procedure clear_interval_in_range: .tier, .lo, .hi
    selectObject: textgrid
    repeat
        .found = 0
        .n = Get number of intervals: .tier
        .i = 2
        while .i <= .n and .found = 0
            .bstart = Get starting point: .tier, .i
            if .bstart > .lo + 1e-6 and .bstart < .hi - 1e-6
                Remove left boundary: .tier, .i
                .found = 1
            endif
            .i = .i + 1
        endwhile
    until .found = 0
endproc

# Wipe this script's marks within a segment: landmark + metadata points,
# vmid interval boundaries. (Does NOT touch the rep/segment tiers.)
procedure clear_segment: .seg_start, .seg_end
    @clear_points_in_range: landmarks_tier, .seg_start, .seg_end
    @clear_points_in_range: metadata_tier, .seg_start, .seg_end
    @clear_interval_in_range: vmid_tier, .seg_start, .seg_end
endproc
