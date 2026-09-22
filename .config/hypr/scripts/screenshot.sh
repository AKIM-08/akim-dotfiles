#!/usr/bin/env bash
# screenshot.sh - Multi-choice Screenshot and Screen Recording tool for Hyprland
# Parity with GNOME Screenshot tool (Selection, Screen, Window, Swappy Annotation, Screen Recording, Color Picker)

set -euo pipefail

DIR="${XDG_SCREENSHOTS_DIR:-$HOME/Pictures/Screenshots}"
VID_DIR="${XDG_VIDEOS_DIR:-$HOME/Videos/Recordings}"
mkdir -p "$DIR" "$VID_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$DIR/screenshot-${TIMESTAMP}.png"
REC_FILE="$VID_DIR/recording-${TIMESTAMP}.mp4"

# Notify and copy helper
post_capture() {
    local target_file="$1"
    local label="${2:-Screenshot}"
    if command -v wl-copy &>/dev/null; then
        wl-copy < "$target_file"
    fi
    if command -v notify-send &>/dev/null; then
        notify-send -a "Screenshot" "$label" "Saved to $(basename "$target_file") and copied to clipboard" -i "$target_file" -u normal
    fi
}

# Capture active window geometry
get_active_window_geom() {
    if command -v hyprctl &>/dev/null; then
        hyprctl activewindow -j 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'at' in data and 'size' in data:
        print(f\"{data['at'][0]},{data['at'][1]} {data['size'][0]}x{data['size'][1]}\")
except Exception:
    sys.exit(1)
"
    fi
}

# 1. Selection (Region)
capture_region() {
    local geom
    geom=$(slurp -d -b "#00000088" -c "#89b4fa" -s "#89b4fa22") || exit 0
    grim -g "$geom" "$FILE"
    post_capture "$FILE" "Region Screenshot"
}

# 2. Entire Screen (Full)
capture_full() {
    # Brief delay if triggered from menu
    sleep 0.2
    grim "$FILE"
    post_capture "$FILE" "Fullscreen Screenshot"
}

# 3. Active Window
capture_window() {
    local geom
    geom=$(get_active_window_geom) || geom=""
    if [ -n "$geom" ]; then
        grim -g "$geom" "$FILE"
        post_capture "$FILE" "Window Screenshot"
    else
        capture_region
    fi
}

# 4. Select a Window (Interactive click)
capture_select_window() {
    local geom
    if command -v hyprctl &>/dev/null; then
        geom=$(hyprctl clients -j | python3 -c "
import sys, json
try:
    clients = json.load(sys.stdin)
    boxes = [f\"{c['at'][0]},{c['at'][1]} {c['size'][0]}x{c['size'][1]}\" for c in clients if c.get('mapped', True)]
    print('\n'.join(boxes))
except Exception:
    pass
" | slurp -d) || exit 0
    else
        geom=$(slurp -d) || exit 0
    fi
    grim -g "$geom" "$FILE"
    post_capture "$FILE" "Window Screenshot"
}

# 5. Region + Swappy Annotation Editor
capture_swappy() {
    local geom
    geom=$(slurp -d -b "#00000088" -c "#89b4fa" -s "#89b4fa22") || exit 0
    if command -v swappy &>/dev/null; then
        grim -g "$geom" - | swappy -f - -o "$FILE"
        if [ -f "$FILE" ]; then
            post_capture "$FILE" "Annotated Screenshot"
        fi
    else
        grim -g "$geom" "$FILE"
        post_capture "$FILE" "Region Screenshot"
    fi
}

# 6. Screen Recording Toggle (wf-recorder / wl-screenrec)
toggle_recording() {
    if pgrep -x wf-recorder &>/dev/null; then
        killall -INT wf-recorder || true
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recording Stopped" "Video saved to $VID_DIR" -i video-x-generic -u normal
        fi
        exit 0
    elif pgrep -x wl-screenrec &>/dev/null; then
        killall -INT wl-screenrec || true
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recording Stopped" "Video saved to $VID_DIR" -i video-x-generic -u normal
        fi
        exit 0
    fi

    # Start recording
    if command -v notify-send &>/dev/null; then
        notify-send -a "Screen Recorder" "Select recording area" "Draw an area or press ESC for fullscreen" -u low
    fi

    local geom=""
    geom=$(slurp -d -b "#ff005533" -c "#ff0055" || true)

    if command -v wf-recorder &>/dev/null; then
        if [ -n "$geom" ]; then
            wf-recorder -g "$geom" -f "$REC_FILE" --audio &
        else
            wf-recorder -f "$REC_FILE" --audio &
        fi
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recording Started" "Press SUPER+SHIFT+R or Screenshot menu to stop" -i media-record -u critical
        fi
    elif command -v wl-screenrec &>/dev/null; then
        if [ -n "$geom" ]; then
            wl-screenrec -g "$geom" -f "$REC_FILE" --audio &
        else
            wl-screenrec -f "$REC_FILE" --audio &
        fi
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recording Started" "Press SUPER+SHIFT+R or Screenshot menu to stop" -i media-record -u critical
        fi
    else
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Error" "Please install wf-recorder or wl-screenrec" -u critical
        fi
    fi
}

# 7. Color Picker
pick_color() {
    if command -v hyprpicker &>/dev/null; then
        local color
        color=$(hyprpicker -a -n) || exit 0
        if [ -n "$color" ] && command -v notify-send &>/dev/null; then
            notify-send -a "Color Picker" "Color Copied" "Hex: $color" -u normal
        fi
    fi
}

# Interactive Rofi Screenshot & Record Menu
show_menu() {
    local is_recording="󰑋  Screen Record (Start / Stop)"
    if pgrep -x wf-recorder &>/dev/null || pgrep -x wl-screenrec &>/dev/null; then
        is_recording="󰓛  STOP Screen Recording (Active)"
    fi

    local opt_region="󰄀  Selection (Marquee Box)"
    local opt_screen="󰍹  Entire Screen"
    local opt_window="󱂬  Active Window"
    local opt_pick_win="󰒉  Select a Window"
    local opt_swappy="󰄄  Selection + Annotate (Swappy)"
    local opt_color="󱃚  Color Picker (Hyprpicker)"

    local selected
    selected=$(printf "%s\n%s\n%s\n%s\n%s\n%s\n%s" \
        "$opt_region" \
        "$opt_screen" \
        "$opt_window" \
        "$opt_pick_win" \
        "$opt_swappy" \
        "$is_recording" \
        "$opt_color" | \
        rofi -dmenu -i -p "󰄀 Capture" -theme "$HOME/.config/rofi/screenshot.rasi")

    case "$selected" in
        *"Selection (Marquee"*) capture_region ;;
        *"Entire Screen"*)       capture_full ;;
        *"Active Window"*)       capture_window ;;
        *"Select a Window"*)     capture_select_window ;;
        *"Selection + Annotate"*) capture_swappy ;;
        *"Screen Record"*|*"STOP Screen Recording"*) toggle_recording ;;
        *"Color Picker"*)        pick_color ;;
    esac
}

# Action dispatch
MODE="${1:-menu}"

case "$MODE" in
    menu|"")
        show_menu
        ;;
    region|area|selection)
        capture_region
        ;;
    full|screen)
        capture_full
        ;;
    window)
        capture_window
        ;;
    window-select|select-window)
        capture_select_window
        ;;
    swappy|edit)
        capture_swappy
        ;;
    record|toggle-record|recording)
        toggle_recording
        ;;
    color|colorpicker)
        pick_color
        ;;
    *)
        echo "Usage: $0 [menu|region|full|window|window-select|swappy|record|color]" >&2
        exit 1
        ;;
esac
