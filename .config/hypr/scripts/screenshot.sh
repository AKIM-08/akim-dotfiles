#!/usr/bin/env bash
# screenshot.sh - Multi-choice Screenshot and Screen Recording tool for Hyprland
# Clean transparent selection marquee, Swappy annotation, Screen Recording, and Color Picker with fallbacks.

set -euo pipefail

DIR="${XDG_SCREENSHOTS_DIR:-$HOME/Pictures/Screenshots}"
VID_DIR="${XDG_VIDEOS_DIR:-$HOME/Videos/Recordings}"
mkdir -p "$DIR" "$VID_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$DIR/screenshot-${TIMESTAMP}.png"
REC_FILE="$VID_DIR/recording-${TIMESTAMP}.mp4"

# Slurp appearance: Clean subtle dark dim outside, white crisp border, 100% TRANSPARENT inside (no blue tint)
SLURP_ARGS=(-d -b "#00000055" -c "#ffffff" -s "#00000000" -w 2)

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

# 1. Selection (Region) - 100% transparent marquee selection
capture_region() {
    local geom
    geom=$(slurp "${SLURP_ARGS[@]}") || exit 0
    grim -g "$geom" "$FILE"
    post_capture "$FILE" "Region Screenshot"
}

# 2. Entire Screen (Full)
capture_full() {
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
" | slurp "${SLURP_ARGS[@]}") || exit 0
    else
        geom=$(slurp "${SLURP_ARGS[@]}") || exit 0
    fi
    grim -g "$geom" "$FILE"
    post_capture "$FILE" "Window Screenshot"
}

# 5. Region + Draw / Annotate (Swappy Editor)
capture_swappy() {
    local geom
    geom=$(slurp "${SLURP_ARGS[@]}") || exit 0
    if command -v swappy &>/dev/null; then
        grim -g "$geom" - | swappy -f - -o "$FILE"
        if [ -f "$FILE" ]; then
            post_capture "$FILE" "Annotated Screenshot"
        fi
    else
        grim -g "$geom" "$FILE"
        post_capture "$FILE" "Region Screenshot"
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screenshot" "Tip" "Install swappy to draw arrows/text on screenshots: sudo apt install swappy" -u low
        fi
    fi
}

# 6. Screen Recording Toggle (wf-recorder / wl-screenrec)
toggle_recording() {
    # If already running, stop recording
    if pgrep -x wf-recorder &>/dev/null; then
        pkill -INT -x wf-recorder || true
        sleep 0.5
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recording Stopped" "Video saved to $VID_DIR" -i video-x-generic -u normal
        fi
        exit 0
    elif pgrep -x wl-screenrec &>/dev/null; then
        pkill -INT -x wl-screenrec || true
        sleep 0.5
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recording Stopped" "Video saved to $VID_DIR" -i video-x-generic -u normal
        fi
        exit 0
    fi

    # Check recorder availability
    local RECORDER=""
    if command -v wf-recorder &>/dev/null; then
        RECORDER="wf-recorder"
    elif command -v wl-screenrec &>/dev/null; then
        RECORDER="wl-screenrec"
    fi

    if [ -z "$RECORDER" ]; then
        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" "Recorder Not Installed" "Install wf-recorder: <b>sudo apt install wf-recorder</b>" -u critical
        fi
        exit 1
    fi

    # Optional region select (Press ESC or click for full screen)
    local geom=""
    geom=$(slurp -d -b "#00000055" -c "#ff3366" -s "#00000000" -w 2 || true)

    if [ "$RECORDER" = "wf-recorder" ]; then
        if [ -n "$geom" ]; then
            wf-recorder -g "$geom" -f "$REC_FILE" &
        else
            wf-recorder -f "$REC_FILE" &
        fi
    else
        if [ -n "$geom" ]; then
            wl-screenrec -g "$geom" -f "$REC_FILE" &
        else
            wl-screenrec -f "$REC_FILE" &
        fi
    fi

    if command -v notify-send &>/dev/null; then
        notify-send -a "Screen Recorder" "Recording Started" "Press SUPER+SHIFT+R or open menu to stop" -i media-record -u critical
    fi
}

# 7. Color Picker (Hyprpicker with Python/PIL fallback)
pick_color() {
    local color=""
    if command -v hyprpicker &>/dev/null; then
        color=$(hyprpicker -n 2>/dev/null || true)
    fi

    # Fallback to grim + slurp single pixel + python PIL if hyprpicker is unavailable
    if [ -z "$color" ]; then
        local pt
        pt=$(slurp -p -d -b "#00000055" -c "#ffffff" || true)
        if [ -n "$pt" ]; then
            local tmp_pixel="/tmp/pixel_pick.png"
            grim -g "$pt" "$tmp_pixel" 2>/dev/null
            if [ -f "$tmp_pixel" ]; then
                color=$(python3 -c "
from PIL import Image
try:
    im = Image.open('$tmp_pixel')
    px = im.getpixel((0,0))
    print('#{:02x}{:02x}{:02x}'.format(px[0], px[1], px[2]))
except Exception:
    pass
" 2>/dev/null || true)
                rm -f "$tmp_pixel"
            fi
        fi
    fi

    if [ -n "$color" ]; then
        if command -v wl-copy &>/dev/null; then
            echo -n "$color" | wl-copy
        fi
        if command -v notify-send &>/dev/null; then
            notify-send -a "Color Picker" "Color Copied" "Hex: <b>$color</b>" -u normal
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
    local opt_swappy="󰄄  Selection + Draw / Annotate"
    local opt_color="󱃚  Color Picker (Magnifier)"

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
        *"Selection + Draw"*)    capture_swappy ;;
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
    swappy|edit|draw)
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
