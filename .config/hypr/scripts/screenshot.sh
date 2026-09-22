#!/usr/bin/env bash
# screenshot.sh - Multi-choice Screenshot and Screen Recording tool for Hyprland
# Features:
# - Full toggle support (SUPER+SHIFT+P or SUPER+P opens and closes menu)
# - Clean transparent marquee selection
# - Persistent on-screen red bounding box during region video recording
# - Audio source selection: Device / System Audio, Microphone, Both, or No Audio

set -euo pipefail

DIR="${XDG_SCREENSHOTS_DIR:-$HOME/Pictures/Screenshots}"
VID_DIR="${XDG_VIDEOS_DIR:-$HOME/Videos/Recordings}"
mkdir -p "$DIR" "$VID_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$DIR/screenshot-${TIMESTAMP}.png"
REC_FILE="$VID_DIR/recording-${TIMESTAMP}.mp4"
LOOPBACK_FILE="/tmp/wf_loopback_module.id"

# Slurp appearance: Dark dim outside, crisp white border, 100% transparent inside
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

# 1. Selection (Region)
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
        grim -g "$geom" - | env GTK_THEME=Adwaita:dark swappy -f - -o "$FILE" 2>/dev/null || grim -g "$geom" - | swappy -f - -o "$FILE"
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

# 6. Screen Recording Toggle with Audio Source and Persistent Red Border
toggle_recording() {
    # If already running, STOP recording and clean up
    if pgrep -x wf-recorder &>/dev/null || pgrep -x wl-screenrec &>/dev/null; then
        pkill -INT -x wf-recorder 2>/dev/null || true
        pkill -INT -x wl-screenrec 2>/dev/null || true
        pkill -f "record-border.py" 2>/dev/null || true
        
        # Unload temp loopback module if used
        if [ -f "$LOOPBACK_FILE" ]; then
            local mod_id
            mod_id=$(cat "$LOOPBACK_FILE" 2>/dev/null || true)
            if [ -n "$mod_id" ] && command -v pactl &>/dev/null; then
                pactl unload-module "$mod_id" 2>/dev/null || true
            fi
            rm -f "$LOOPBACK_FILE"
        fi

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

    # 1. Ask for Audio Choice via quick rofi menu
    local opt_sys="󰓃  Device / System Audio (Desktop Sounds)"
    local opt_mic="󰍬  Microphone (Voice)"
    local opt_both="󰓃󰍬 Both (System Audio + Microphone)"
    local opt_none="󰝟  No Audio (Muted Video)"

    local audio_choice
    audio_choice=$(printf "%s\n%s\n%s\n%s" "$opt_sys" "$opt_mic" "$opt_both" "$opt_none" | \
        rofi -dmenu -i -p "󰍬 Audio Source" -theme "$HOME/.config/rofi/screenshot.rasi" || true)

    if [ -z "$audio_choice" ]; then
        # User cancelled audio prompt
        exit 0
    fi

    local AUDIO_ARGS=()
    local DEFAULT_SINK=""
    local DEFAULT_SOURCE=""

    if command -v pactl &>/dev/null; then
        DEFAULT_SINK=$(pactl get-default-sink 2>/dev/null || true)
        DEFAULT_SOURCE=$(pactl get-default-source 2>/dev/null || true)
    fi

    case "$audio_choice" in
        *"Device / System"*)
            if [ -n "$DEFAULT_SINK" ]; then
                AUDIO_ARGS=(--audio="${DEFAULT_SINK}.monitor")
            else
                AUDIO_ARGS=(--audio)
            fi
            ;;
        *"Microphone"*)
            if [ -n "$DEFAULT_SOURCE" ]; then
                AUDIO_ARGS=(--audio="${DEFAULT_SOURCE}")
            else
                AUDIO_ARGS=(--audio)
            fi
            ;;
        *"Both"*)
            if [ -n "$DEFAULT_SOURCE" ] && [ -n "$DEFAULT_SINK" ] && command -v pactl &>/dev/null; then
                # Route mic to sink monitor via loopback
                local mod_id
                mod_id=$(pactl load-module module-loopback latency_msec=20 source="$DEFAULT_SOURCE" sink="$DEFAULT_SINK" 2>/dev/null || true)
                if [ -n "$mod_id" ]; then
                    echo "$mod_id" > "$LOOPBACK_FILE"
                fi
                AUDIO_ARGS=(--audio="${DEFAULT_SINK}.monitor")
            else
                AUDIO_ARGS=(--audio)
            fi
            ;;
        *"No Audio"*)
            AUDIO_ARGS=()
            ;;
    esac

    # 2. Select region or ESC for fullscreen
    if command -v notify-send &>/dev/null; then
        notify-send -a "Screen Recorder" "Select recording area" "Draw an area or press ESC for fullscreen" -u low
    fi

    local geom=""
    geom=$(slurp -d -b "#00000055" -c "#ff3366" -s "#00000000" -w 2 || true)

    # 3. If region selected, launch persistent red border overlay
    if [ -n "$geom" ]; then
        # Parse x, y, width, height from geom format "X,Y WxH"
        local pos=${geom% *}
        local dim=${geom#* }
        local gx=${pos%,*}
        local gy=${pos#*,}
        local gw=${dim%x*}
        local gh=${dim#*x}

        python3 "$HOME/.config/hypr/scripts/record-border.py" "$gx" "$gy" "$gw" "$gh" &
    fi

    # 4. Start recording process
    if [ "$RECORDER" = "wf-recorder" ]; then
        if [ -n "$geom" ]; then
            wf-recorder -g "$geom" -f "$REC_FILE" "${AUDIO_ARGS[@]}" &
        else
            wf-recorder -f "$REC_FILE" "${AUDIO_ARGS[@]}" &
        fi
    else
        if [ -n "$geom" ]; then
            wl-screenrec -g "$geom" -f "$REC_FILE" "${AUDIO_ARGS[@]}" &
        else
            wl-screenrec -f "$REC_FILE" "${AUDIO_ARGS[@]}" &
        fi
    fi

    if command -v notify-send &>/dev/null; then
        notify-send -a "Screen Recorder" "Recording Started" "Press SUPER+SHIFT+P, SUPER+SHIFT+R, or Screenshot menu to stop" -i media-record -u critical
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

# Interactive Rofi Screenshot & Record Menu (with toggle support)
show_menu() {
    # If menu is already open, toggle it off!
    if pgrep -x rofi >/dev/null; then
        pkill -x rofi
        exit 0
    fi

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
