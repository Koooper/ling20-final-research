# 03_export_spectrograms.praat
#
# Stage D (optional, compute-heavy) of the Lakota obstruents pipeline. Walks the
# per-word WAV + annotated 6-tier TextGrid files produced by 00/01 and renders a
# figure per labeled target segment: a configurable STACK of panels (oscillogram,
# spectrogram, pitch, intensity) sharing one time axis, with the committed
# landmarks (t_clo, t_burst, t_glot_rel, t_voi, t_vend, t_pvend), the vmid
# steady-state interval, and the segment bounds drawn in.
#
# MODULAR LAYOUT
#   Panels  = space-separated list, drawn top-to-bottom. Supported kinds:
#             oscillogram  spectrogram  pitch  intensity
#   Layout  = stacked  -> one image per token  ({token_id}.png)
#             separate -> one image per panel  ({token_id}_{kind}.png)
#   Formants can be overlaid on the spectrogram (red speckles) via a flag.
#   To add a new panel kind: write a panel_<kind> proc + add a case to draw_panel
#   + give it a height + set its need_* flag. Nothing else changes.
#
# PREVIEW: by default the first matching token is rendered (shown in the Picture
#   window + saved), then a dialog asks whether to render the rest -- so you can
#   eyeball the layout before committing to the whole directory.
#
# Kept SEPARATE from 02 because rendering images is slow; run it whenever you like.
# Reads ONLY committed annotations (never places boundaries) and is idempotent: an
# existing PNG is left alone unless "Overwrite existing images" is ticked.
#
# The image file name embeds token_id == the SAME join key 02 emits, so images
# line up 1:1 with measurement rows.
#
# TIERS (per-word file): 1 word  2 rep  3 segment  4 vmid  5 landmarks  6 metadata
# OUTPUT  figures/spectrograms/{speaker}/...   (300-dpi PNG)

form: "Export figures (Lakota obstruents)"
    folder: "Words directory", "C:/Users/djjr6/OneDrive/Documents/LakotaPhoneticsResearch/data/words/S1"
    folder: "Figures base dir", "C:/Users/djjr6/OneDrive/Documents/LakotaPhoneticsResearch/figures/spectrograms"
    word: "Speaker id", "S1"
    natural: "Word tier", "1"
    natural: "Rep tier", "2"
    natural: "Segment tier", "3"
    natural: "Vmid tier", "4"
    natural: "Landmarks tier", "5"
    natural: "Metadata tier", "6"
    comment: "Panels = which stacked panels to draw, top to bottom (space-separated):"
    comment: "   oscillogram  spectrogram  pitch  intensity"
    sentence: "Panels", "oscillogram spectrogram"
    optionmenu: "Layout", 1
        option: "stacked (all panels in one image)"
        option: "separate (one image per panel)"
    boolean: "Overlay formants on spectrogram", 0
    comment: "Spectrogram (wideband for obstruents): 0.005 s window, 8 kHz top."
    positive: "Window length (s)", "0.005"
    positive: "Max frequency (Hz)", "8000"
    real: "Dynamic range (dB)", "50"
    positive: "Formant ceiling (Hz)", "5000"
    positive: "Pitch floor (Hz)", "75"
    positive: "Pitch ceiling (Hz)", "300"
    comment: "Panel sizes (inches): tweak if the figure feels cramped or stretched."
    positive: "Panel width (in)", "6.5"
    positive: "Oscillogram height (in)", "1.4"
    positive: "Spectrogram height (in)", "3.0"
    positive: "Aux panel height (in)", "1.4"
    comment: "Time window drawn around each segment:"
    positive: "Padding (ms)", "100"
    positive: "Minimum window (s)", "0.75"
    comment: "Run options:"
    boolean: "Preview first (render one, then confirm)", 1
    boolean: "Accepted only (skip skip/garbage/partial)", 1
    boolean: "Overwrite existing images", 0
endform

pad = padding / 1000
spec_time_step = 0.002
spec_freq_step = 20
title_h = 0.45

# --- validate the panel list + work out which analysis objects we need ---
panels$# = splitByWhitespace$# (panels$)
n_panels = size (panels$#)
if n_panels = 0
    exitScript: "No panels requested. Set Panels to e.g. ""oscillogram spectrogram""."
endif
need_spec = 0
need_pitch = 0
need_int = 0
for p to n_panels
    .k$ = panels$# [p]
    if .k$ = "oscillogram"
        # only needs the Sound
    elsif .k$ = "spectrogram"
        need_spec = 1
    elsif .k$ = "pitch"
        need_pitch = 1
    elsif .k$ = "intensity"
        need_int = 1
    else
        exitScript: "Unknown panel kind '", .k$, "'. Use: oscillogram spectrogram pitch intensity"
    endif
endfor
need_formant = 0
if overlay_formants_on_spectrogram = 1 and need_spec = 1
    need_formant = 1
endif

if not folderExists (words_directory$)
    exitScript: "Words directory does not exist: ", words_directory$
endif
out_dir$ = figures_base_dir$ + "/" + speaker_id$
createFolder: out_dir$

appendInfoLine: "=== export_figures (Lakota obstruents) ==="
appendInfoLine: "Speaker: ", speaker_id$, "  Panels: ", panels$, "  Output: ", out_dir$

files$# = fileNames$# (words_directory$ + "/*.wav")
n_files = size (files$#)
if n_files = 0
    exitScript: "No .wav files found in ", words_directory$
endif

# Picture-window defaults (set once; reproducible regardless of GUI state).
Erase all
Times
Font size: 10
Line width: 1

n_written = 0
n_skipped = 0
confirmed = 0
abort = 0

for f to n_files
    if abort = 0
        wavname$ = files$# [f]
        basename$ = left$ (wavname$, rindex (wavname$, ".") - 1)
        tg_path$ = words_directory$ + "/" + basename$ + ".TextGrid"

        if not fileReadable (tg_path$)
            appendInfoLine: "No TextGrid for ", wavname$, " - skipping"
        else
            sound = Read from file: words_directory$ + "/" + wavname$
            file_dur = Get total duration
            textgrid = Read from file: tg_path$

            # analysis objects (only what the requested panels need), once per file
            if need_spec = 1
                selectObject: sound
                spectrogram = noprogress To Spectrogram: window_length, max_frequency,
                    ... spec_time_step, spec_freq_step, "Gaussian"
            endif
            if need_pitch = 1
                selectObject: sound
                pitch = noprogress To Pitch: 0, pitch_floor, pitch_ceiling
            endif
            if need_int = 1
                selectObject: sound
                intensity = noprogress To Intensity: 100, 0, "yes"
            endif
            if need_formant = 1
                selectObject: sound
                formant = noprogress To Formant (burg): 0, 5, formant_ceiling, 0.025, 50
            endif

            @process_file

            removeObject: sound, textgrid
            if need_spec = 1
                removeObject: spectrogram
            endif
            if need_pitch = 1
                removeObject: pitch
            endif
            if need_int = 1
                removeObject: intensity
            endif
            if need_formant = 1
                removeObject: formant
            endif
        endif
    endif
endfor

if abort = 1
    appendInfoLine: "Stopped after preview. Wrote ", n_written, " image(s)."
else
    appendInfoLine: "Wrote ", n_written, " image(s); skipped ", n_skipped, " existing."
endif
appendInfoLine: "=== done ==="

# ============================================================
# FILE DRIVER
# ============================================================
procedure process_file
    selectObject: textgrid
    .n_seg = Get number of intervals: segment_tier
    for .i to .n_seg
        if abort = 0
            selectObject: textgrid
            .lab$ = Get label of interval: segment_tier, .i
            if .lab$ <> ""
                .s = Get starting point: segment_tier, .i
                .e = Get end point: segment_tier, .i
                @maybe_render: .lab$, .s, .e
            endif
        endif
    endfor
endproc

# ============================================================
# ONE SEGMENT -> decide, render, (preview gate)
# ============================================================
procedure maybe_render: .seg_label$, .seg_start, .seg_end
    .mid = (.seg_start + .seg_end) / 2
    @label_at: rep_tier, .mid
    .rep_label$ = label_at.result$
    @label_at: word_tier, .mid
    .word$ = label_at.result$

    @read_status: .seg_start, .seg_end
    .sound_type$ = read_status.type$
    .status$ = read_status.status$

    .token_id$ = speaker_id$ + "_" + basename$ + "_" + .rep_label$ + "_" + .seg_label$
    if layout = 1
        .probe$ = out_dir$ + "/" + .token_id$ + ".png"
    else
        .probe$ = out_dir$ + "/" + .token_id$ + "_" + panels$# [1] + ".png"
    endif

    .render = 1
    if accepted_only = 1 and .status$ <> "accepted"
        .render = 0
    endif
    if .render = 1 and overwrite_existing_images = 0 and fileReadable (.probe$)
        n_skipped = n_skipped + 1
        .render = 0
    endif

    if .render = 1
        @read_landmarks: .seg_start, .seg_end
        @find_interval: vmid_tier, .seg_start, .seg_end
        .vms = find_interval.start
        .vme = find_interval.end

        # draw window: segment +/- padding, never narrower than the minimum
        # (keeps resolution readable, avoids the "stars" zoom). Centre on the
        # segment, widen to the floor, then SHIFT to stay inside the file so an
        # edge token keeps full width instead of being clamped/squished.
        .c = (.seg_start + .seg_end) / 2
        .win = (.seg_end - .seg_start) + 2 * pad
        if .win < minimum_window
            .win = minimum_window
        endif
        if .win >= file_dur
            .lo = 0
            .hi = file_dur
        else
            .lo = .c - .win / 2
            .hi = .c + .win / 2
            if .lo < 0
                .hi = .hi - .lo
                .lo = 0
            endif
            if .hi > file_dur
                .lo = .lo - (.hi - file_dur)
                .hi = file_dur
            endif
        endif

        @build_title: .token_id$, .word$, .sound_type$, .status$
        if layout = 1
            @render_stacked: .lo, .hi, .seg_start, .seg_end, .vms, .vme,
                ... build_title.result$, .token_id$
        else
            @render_separate: .lo, .hi, .seg_start, .seg_end, .vms, .vme,
                ... build_title.result$, .token_id$
        endif

        if preview_first = 1 and confirmed = 0
            confirmed = 1
            beginPause: "Preview"
                comment: "Drew one example (see the Picture window), saved to:"
                comment: .probe$
                comment: "Happy with the layout? Continue rendering the rest of the directory?"
                comment: "(Stop = keep just this example and quit.)"
            .c2 = endPause: "Stop", "Continue", 2, 1
            if .c2 = 1
                abort = 1
            endif
        endif
    endif
endproc

# ============================================================
# FIGURE ASSEMBLY
# ============================================================
# All panels in one image, stacked, sharing a time axis (bottom panel only).
procedure render_stacked: .lo, .hi, .ss, .se, .vms, .vme, .title$, .tid$
    Erase all
    Black
    Solid line
    Line width: 1

    .total_h = title_h
    for .p to n_panels
        @panel_height: panels$# [.p]
        .total_h = .total_h + panel_height.result
    endfor

    @draw_title_band: 0, panel_width, 0, title_h, .title$
    .y = title_h
    for .p to n_panels
        @panel_height: panels$# [.p]
        .ph = panel_height.result
        .is_bottom = 0
        if .p = n_panels
            .is_bottom = 1
        endif
        .with_labels = 0
        if .p = 1
            .with_labels = 1
        endif
        @draw_panel: panels$# [.p], 0, panel_width, .y, .y + .ph,
            ... .lo, .hi, .is_bottom, .with_labels, .ss, .se, .vms, .vme
        .y = .y + .ph
    endfor

    Select outer viewport: 0, panel_width, 0, .total_h
    Save as 300-dpi PNG file: out_dir$ + "/" + .tid$ + ".png"
    n_written = n_written + 1
    appendInfoLine: "IMG: ", .tid$
endproc

# Each panel as its own image (own title + own time axis + own marks).
procedure render_separate: .lo, .hi, .ss, .se, .vms, .vme, .title$, .tid$
    for .p to n_panels
        Erase all
        Black
        Solid line
        Line width: 1
        @panel_height: panels$# [.p]
        .ph = panel_height.result
        @draw_title_band: 0, panel_width, 0, title_h, .title$ + "    {" + panels$# [.p] + "}"
        @draw_panel: panels$# [.p], 0, panel_width, title_h, title_h + .ph,
            ... .lo, .hi, 1, 1, .ss, .se, .vms, .vme
        Select outer viewport: 0, panel_width, 0, title_h + .ph
        Save as 300-dpi PNG file: out_dir$ + "/" + .tid$ + "_" + panels$# [.p] + ".png"
        n_written = n_written + 1
        appendInfoLine: "IMG: ", .tid$, "_", panels$# [.p]
    endfor
endproc

procedure panel_height: .kind$
    if .kind$ = "oscillogram"
        .result = oscillogram_height
    elsif .kind$ = "spectrogram"
        .result = spectrogram_height
    else
        .result = aux_panel_height
    endif
endproc

# Title band (inner viewport -> no axis gutter, fills the strip).
procedure draw_title_band: .left, .right, .top, .bottom, .title$
    Select inner viewport: .left, .right, .top, .bottom
    Axes: 0, 1, 0, 1
    Black
    Font size: 11
    Text: 0.5, "Centre", 0.5, "Half", .title$
    Font size: 10
endproc

# ============================================================
# PANEL DISPATCH  (draw content, then overlay shared marks)
# ============================================================
procedure draw_panel: .kind$, .left, .right, .top, .bottom,
        ... .lo, .hi, .is_bottom, .with_labels, .ss, .se, .vms, .vme
    if .kind$ = "oscillogram"
        @panel_oscillogram: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
        .ylo = panel_oscillogram.ylo
        .yhi = panel_oscillogram.yhi
    elsif .kind$ = "spectrogram"
        @panel_spectrogram: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
        .ylo = panel_spectrogram.ylo
        .yhi = panel_spectrogram.yhi
    elsif .kind$ = "pitch"
        @panel_pitch: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
        .ylo = panel_pitch.ylo
        .yhi = panel_pitch.yhi
    elsif .kind$ = "intensity"
        @panel_intensity: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
        .ylo = panel_intensity.ylo
        .yhi = panel_intensity.yhi
    endif
    @marks_on_panel: .ss, .se, .vms, .vme, .ylo, .yhi, .with_labels
endproc

procedure panel_oscillogram: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
    Select outer viewport: .left, .right, .top, .bottom
    selectObject: sound
    .amax = Get maximum: .lo, .hi, "None"
    .amin = Get minimum: .lo, .hi, "None"
    .a = .amax
    if abs (.amin) > .a
        .a = abs (.amin)
    endif
    if .a <= 0
        .a = 1
    endif
    .ylo = - 1.1 * .a
    .yhi = 1.1 * .a
    Draw: .lo, .hi, .ylo, .yhi, "no", "Curve"
    Draw inner box
    Colour: "{0.6,0.6,0.6}"
    Dotted line
    Draw line: .lo, 0, .hi, 0
    Solid line
    Black
    Text left: "yes", "Amplitude"
    if .is_bottom = 1
        @time_axis: .lo, .hi
    endif
endproc

procedure panel_spectrogram: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
    Select outer viewport: .left, .right, .top, .bottom
    selectObject: spectrogram
    Paint: .lo, .hi, 0, max_frequency, 100, "yes", dynamic_range, 6, 0, "no"
    if need_formant = 1
        selectObject: formant
        Colour: "Red"
        Speckle: .lo, .hi, max_frequency, 30, "no"
        Black
    endif
    Draw inner box
    Marks left every: 1, 1000, "yes", "yes", "no"
    Text left: "yes", "Frequency (Hz)"
    if .is_bottom = 1
        @time_axis: .lo, .hi
    endif
    .ylo = 0
    .yhi = max_frequency
endproc

procedure panel_pitch: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
    Select outer viewport: .left, .right, .top, .bottom
    selectObject: pitch
    Draw: .lo, .hi, pitch_floor, pitch_ceiling, "no"
    Draw inner box
    Marks left every: 1, 100, "yes", "yes", "no"
    Text left: "yes", "F0 (Hz)"
    if .is_bottom = 1
        @time_axis: .lo, .hi
    endif
    .ylo = pitch_floor
    .yhi = pitch_ceiling
endproc

procedure panel_intensity: .left, .right, .top, .bottom, .lo, .hi, .is_bottom
    Select outer viewport: .left, .right, .top, .bottom
    selectObject: intensity
    .imin = Get minimum: .lo, .hi, "Parabolic"
    .imax = Get maximum: .lo, .hi, "Parabolic"
    if .imin = undefined or .imax = undefined or .imax <= .imin
        .ylo = 0
        .yhi = 100
    else
        .m = 0.1 * (.imax - .imin) + 1
        .ylo = .imin - .m
        .yhi = .imax + .m
    endif
    Draw: .lo, .hi, .ylo, .yhi, "no"
    Draw inner box
    Marks left every: 1, 20, "yes", "yes", "no"
    Text left: "yes", "Intensity (dB)"
    if .is_bottom = 1
        @time_axis: .lo, .hi
    endif
endproc

# Adaptive time-tick spacing: a handful of labels, never a wall of them.
procedure time_axis: .lo, .hi
    .w = .hi - .lo
    if .w <= 0.3
        .tstep = 0.05
    elsif .w <= 0.8
        .tstep = 0.1
    elsif .w <= 2
        .tstep = 0.25
    elsif .w <= 5
        .tstep = 0.5
    else
        .tstep = 1
    endif
    Marks bottom every: 1, .tstep, "yes", "yes", "no"
    Text bottom: "yes", "Time (s)"
endproc

# Draw segment bounds + vmid + landmarks onto whatever panel is current.
# .ylo/.yhi = the panel's world y-range; .with_label = 1 to tag landmarks.
procedure marks_on_panel: .ss, .se, .vms, .vme, .ylo, .yhi, .with_label
    Line width: 1
    # segment bounds (gray dashed)
    Colour: "{0.5,0.5,0.5}"
    Dashed line
    Draw line: .ss, .ylo, .ss, .yhi
    Draw line: .se, .ylo, .se, .yhi
    # vmid steady-state interval (green dotted)
    if .vms >= 0 and .vme >= 0
        Colour: "{0,0.6,0}"
        Dotted line
        Draw line: .vms, .ylo, .vms, .yhi
        Draw line: .vme, .ylo, .vme, .yhi
        if .with_label = 1
            @panel_label: (.vms + .vme) / 2, .ylo + 0.72 * (.yhi - .ylo), "vmid"
        endif
    endif
    # landmarks (red dotted), labels staggered over three heights to limit overlap
    Colour: "Red"
    Dotted line
    lbl_lvl = 0
    @draw_lm: t_clo, "clo", .ylo, .yhi, .with_label
    @draw_lm: t_burst, "bur", .ylo, .yhi, .with_label
    @draw_lm: t_glot, "glt", .ylo, .yhi, .with_label
    @draw_lm: t_voi, "voi", .ylo, .yhi, .with_label
    @draw_lm: t_vend, "ven", .ylo, .yhi, .with_label
    @draw_lm: t_pvend, "pv", .ylo, .yhi, .with_label
    # reset picture state for the caller
    Solid line
    Black
    Line width: 1
endproc

procedure draw_lm: .t, .tag$, .ylo, .yhi, .with_label
    if .t >= 0
        Draw line: .t, .ylo, .t, .yhi
        if .with_label = 1
            lbl_lvl = lbl_lvl + 1
            if lbl_lvl > 3
                lbl_lvl = 1
            endif
            if lbl_lvl = 1
                .frac = 0.96
            elsif lbl_lvl = 2
                .frac = 0.88
            else
                .frac = 0.80
            endif
            @panel_label: .t, .ylo + .frac * (.yhi - .ylo), .tag$
        endif
    endif
endproc

# Small centered label in the current colour (ties label to its line).
procedure panel_label: .x, .y, .tag$
    Font size: 8
    Text: .x, "Centre", .y, "Half", .tag$
    Font size: 10
endproc

# Escape Praat picture-text style markup so strings print literally.
# Backslash MUST go first (later steps inject their own backslashes).
procedure escape_text: .s$
    .result$ = replace$ (.s$, "\", "\bs", 0)
    .result$ = replace$ (.result$, "_", "\_ ", 0)
    .result$ = replace$ (.result$, "^", "\^ ", 0)
    .result$ = replace$ (.result$, "%", "\% ", 0)
    .result$ = replace$ (.result$, "#", "\# ", 0)
endproc

procedure build_title: .tid$, .word$, .stype$, .status$
    @escape_text: .tid$
    .a$ = escape_text.result$
    @escape_text: .word$
    .b$ = escape_text.result$
    @escape_text: .stype$
    .c$ = escape_text.result$
    @escape_text: .status$
    .d$ = escape_text.result$
    .result$ = .a$ + "    " + .b$ + "    [" + .c$ + "]    (" + .d$ + ")"
endproc

# ============================================================
# TEXTGRID READ HELPERS  (shared logic with 02)
# ============================================================
# Sets landmark globals; -1 = absent. Closed-right (t_vend often sits on seg_end).
procedure read_landmarks: .lo, .hi
    t_clo = -1
    t_burst = -1
    t_voi = -1
    t_vend = -1
    t_glot = -1
    t_pvend = -1
    selectObject: textgrid
    .np = Get number of points: landmarks_tier
    for .p to .np
        .pt = Get time of point: landmarks_tier, .p
        if .pt >= .lo and .pt <= .hi
            .plab$ = Get label of point: landmarks_tier, .p
            if .plab$ = "t_clo"
                t_clo = .pt
            elsif .plab$ = "t_burst"
                t_burst = .pt
            elsif .plab$ = "t_voi"
                t_voi = .pt
            elsif .plab$ = "t_vend"
                t_vend = .pt
            elsif .plab$ = "t_glot_rel"
                t_glot = .pt
            elsif .plab$ = "t_pvend"
                t_pvend = .pt
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

# Labeled interval on .tier whose midpoint lies in [.lo,.hi); start/end = -1 if none.
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

# Read ok:* / skip / garbage on the metadata tier; sets .type$ and .status$.
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
