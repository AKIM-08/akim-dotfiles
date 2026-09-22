#!/usr/bin/env bash
# screenshot.sh - Multi-choice Screenshot and Screen Recording tool for Hyprland
# Features:
# - Full toggle support (SUPER+P opens and closes menu, SUPER+SHIFT+P captures region)
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

REC_META="/tmp/wf_rec_active.info"

# Helper: Unload any active loopback modules to prevent mic bleeding into desktop/speaker audio
cleanup_loopback() {
    if [ -f "$LOOPBACK_FILE" ]; then
        local mod_id
        mod_id=$(cat "$LOOPBACK_FILE" 2>/dev/null || true)
        if [ -n "$mod_id" ] && command -v pactl &>/dev/null; then
            pactl unload-module "$mod_id" 2>/dev/null || true
        fi
        rm -f "$LOOPBACK_FILE"
    fi
    if command -v pactl &>/dev/null; then
        pactl list short modules 2>/dev/null | awk '/module-loopback/ {print $1}' | while read -r mid; do
            [ -n "$mid" ] && pactl unload-module "$mid" 2>/dev/null || true
        done
    fi
}

# 6. Screen Recording Toggle with Audio Source and Persistent Red Border
toggle_recording() {
    # If already running, STOP recording, filter noise, and clean up
    if pgrep -x wf-recorder &>/dev/null || pgrep -x wl-screenrec &>/dev/null; then
        pkill -INT -x wf-recorder 2>/dev/null || true
        pkill -INT -x wl-screenrec 2>/dev/null || true
        pkill -f "record-border.py" 2>/dev/null || true
        
        cleanup_loopback

        local saved_mode=""
        local saved_file=""
        if [ -f "$REC_META" ]; then
            saved_mode=$(awk -F'|' '{print $1}' "$REC_META" 2>/dev/null || true)
            saved_file=$(awk -F'|' '{print $2}' "$REC_META" 2>/dev/null || true)
            rm -f "$REC_META"
        fi

        # Wait up to 5 seconds for recorder to exit cleanly and flush the MP4 trailer
        local wait_count=0
        while pgrep -x wf-recorder &>/dev/null || pgrep -x wl-screenrec &>/dev/null; do
            sleep 0.2
            wait_count=$((wait_count + 1))
            if [ "$wait_count" -ge 25 ]; then
                pkill -9 -x wf-recorder 2>/dev/null || true
                pkill -9 -x wl-screenrec 2>/dev/null || true
                break
            fi
        done

        echo "[$(date)] Stop requested. File: $saved_file, Mode: $saved_mode" >> /tmp/screenrec.log

        # Advanced noise reduction, fan elimination, and voice clarity filter
        if [ -n "$saved_file" ] && [ -f "$saved_file" ]; then
            case "$saved_mode" in
                *"Microphone"*|*"Both"*)
                    if command -v ffmpeg &>/dev/null; then
                        local tmp_clean="${saved_file%.mp4}_clean.mp4"
                        echo "[$(date)] Running FFmpeg noise suppression on $saved_file" >> /tmp/screenrec.log
                        if ffmpeg -y -i "$saved_file" -c:v copy -af "highpass=f=120,lowpass=f=9000,afftdn=nf=-25,volume=1.3" -c:a aac -b:a 192k "$tmp_clean" >> /tmp/screenrec.log 2>&1; then
                            mv "$tmp_clean" "$saved_file" 2>/dev/null || true
                            echo "[$(date)] FFmpeg noise suppression succeeded" >> /tmp/screenrec.log
                        else
                            echo "[$(date)] FFmpeg noise suppression failed! See log above." >> /tmp/screenrec.log
                            rm -f "$tmp_clean"
                        fi
                    else
                        echo "[$(date)] FFmpeg not installed; skipping audio cleaning." >> /tmp/screenrec.log
                        if command -v notify-send &>/dev/null; then
                            notify-send -a "Screen Recorder" "Fan Noise Warning" "Install ffmpeg to automatically remove fan noise: sudo apt install ffmpeg" -u normal
                        fi
                    fi
                    ;;
            esac
        fi

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
    local opt_mic="󰍬  Microphone (Voice - Noise Filtered)"
    local opt_both="󰓃󰍬 Both (System Audio + Microphone)"
    local opt_none="󰝟  No Audio (Muted Video)"

    local audio_choice
    audio_choice=$(printf "%s\n%s\n%s\n%s" "$opt_sys" "$opt_mic" "$opt_both" "$opt_none" | \
        rofi -dmenu -i -p "󰍬 Audio Source" -theme "$HOME/.config/rofi/screenshot.rasi" || true)

    if [ -z "$audio_choice" ]; then
        # User cancelled audio prompt
        exit 0
    fi

    # Always clear existing loopbacks first so microphone is not leaking into output sinks
    cleanup_loopback

    # Discover devices accurately using wpctl inspect, pw-dump, or pactl
    local AUDIO_TARGET=""
    local SINK_NAME=""
    local MIC_NAME=""
    local MON_NAME=""

    if command -v python3 &>/dev/null; then
        read -r MON_NAME MIC_NAME SINK_NAME <<< "$(python3 -c "
import subprocess, json, sys

def cmd(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ''

mon_target = ''
mic_target = ''
sink_name = ''

# Strategy 1: wpctl inspect (WirePlumber native - highest accuracy)
def wpctl_node(target):
    out = cmd(['wpctl', 'inspect', target])
    for line in out.splitlines():
        line = line.strip()
        if 'node.name' in line and '=' in line:
            return line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
    return ''

wp_mic = wpctl_node('@DEFAULT_AUDIO_SOURCE@')
wp_sink = wpctl_node('@DEFAULT_AUDIO_SINK@')
if wp_mic and 'output' not in wp_mic.lower() and not wp_mic.endswith('.monitor'):
    mic_target = wp_mic
if wp_sink:
    sink_name = wp_sink
    mon_target = f'{wp_sink}.monitor'

# Strategy 2: pw-dump (Native PipeWire JSON)
if not mon_target or not mic_target:
    pw_raw = cmd(['pw-dump'])
    if pw_raw:
        try:
            data = json.loads(pw_raw)
            def_sink = ''
            def_source = ''
            for item in data:
                if item.get('type') == 'PipeWire:Interface:Metadata' and item.get('props', {}).get('metadata.name') == 'default':
                    for meta in item.get('metadata', []):
                        k = meta.get('key', '')
                        v = meta.get('value', {})
                        val_str = v.get('name', '') if isinstance(v, dict) else str(v)
                        if k == 'default.audio.sink':
                            def_sink = val_str
                        elif k == 'default.audio.source':
                            def_source = val_str

            sinks = []
            sources = []
            for item in data:
                if item.get('type') == 'PipeWire:Interface:Node':
                    props = item.get('info', {}).get('props', {})
                    mc = str(props.get('media.class', ''))
                    nn = str(props.get('node.name', ''))
                    if not nn:
                        continue
                    if 'Sink' in mc and not nn.endswith('.monitor'):
                        sinks.append(nn)
                    elif 'Source' in mc and not nn.endswith('.monitor') and 'output' not in nn.lower() and 'sink' not in nn.lower():
                        sources.append(nn)

            if not sink_name and def_sink:
                sink_name = def_sink
                mon_target = f'{def_sink}.monitor'
            elif not mon_target and sinks:
                sink_name = sinks[0]
                mon_target = f'{sinks[0]}.monitor'

            if not mic_target and def_source and not def_source.endswith('.monitor') and 'output' not in def_source.lower():
                mic_target = def_source
            elif not mic_target and sources:
                mic_target = sources[0]
        except Exception:
            pass

# Strategy 3: pactl
if not mon_target or not mic_target:
    p_sink = cmd(['pactl', 'get-default-sink']).strip()
    p_source = cmd(['pactl', 'get-default-source']).strip()
    p_sources = cmd(['pactl', 'list', 'short', 'sources'])

    monitors = []
    mics = []
    for line in p_sources.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            n = parts[1]
            if n.endswith('.monitor'):
                monitors.append(n)
            elif 'input' in n.lower() or not n.endswith('.monitor'):
                mics.append(n)

    if not mon_target:
        if p_sink:
            sink_name = p_sink
            mon_target = f'{p_sink}.monitor'
        elif monitors:
            mon_target = monitors[0]

    if not mic_target:
        if p_source and not p_source.endswith('.monitor') and 'output' not in p_source.lower():
            mic_target = p_source
        elif mics:
            mic_target = mics[0]

# Fallbacks
if not mon_target:
    mon_target = '@DEFAULT_AUDIO_SINK@.monitor'
if not mic_target:
    mic_target = '@DEFAULT_AUDIO_SOURCE@'

print(f'{mon_target} {mic_target} {sink_name}')
" 2>/dev/null || echo "@DEFAULT_AUDIO_SINK@.monitor @DEFAULT_AUDIO_SOURCE@ default")"
    else
        MON_NAME="@DEFAULT_AUDIO_SINK@.monitor"
        MIC_NAME="@DEFAULT_AUDIO_SOURCE@"
    fi

    # Optimize microphone hardware volume to eliminate fan clipping
    case "$audio_choice" in
        *"Microphone"*|*"Both"*)
            if command -v wpctl &>/dev/null; then
                wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0 2>/dev/null || true
                local cur_vol
                cur_vol=$(wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | awk '{print $2}' || echo "0.60")
                if awk "BEGIN {exit !($cur_vol > 0.70)}"; then
                    wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 0.65 2>/dev/null || true
                fi
            fi
            ;;
    esac

    local AUDIO_ARGS=()

    case "$audio_choice" in
        *"Device / System"*)
            AUDIO_TARGET="$MON_NAME"
            ;;
        *"Microphone"*)
            AUDIO_TARGET="$MIC_NAME"
            if [ -z "$AUDIO_TARGET" ] || [[ "$AUDIO_TARGET" == *".monitor"* ]] || [[ "$AUDIO_TARGET" == *"output"* ]]; then
                if command -v pactl &>/dev/null; then
                    AUDIO_TARGET=$(pactl get-default-source 2>/dev/null || true)
                fi
            fi
            ;;
        *"Both"*)
            if [ -n "$MIC_NAME" ] && [ -n "$SINK_NAME" ] && command -v pactl &>/dev/null; then
                local mod_id
                mod_id=$(pactl load-module module-loopback latency_msec=20 source="$MIC_NAME" sink="$SINK_NAME" 2>/dev/null || true)
                if [ -n "$mod_id" ]; then
                    echo "$mod_id" > "$LOOPBACK_FILE"
                fi
            fi
            AUDIO_TARGET="$MON_NAME"
            ;;
        *"No Audio"*)
            AUDIO_TARGET=""
            ;;
    esac

    if [ -n "$AUDIO_TARGET" ]; then
        if [ "$RECORDER" = "wf-recorder" ]; then
            AUDIO_ARGS=(--audio="$AUDIO_TARGET")
        else
            AUDIO_ARGS=(--audio --audio-device "$AUDIO_TARGET")
        fi
    fi

    # Record metadata and debug log
    echo "${audio_choice}|${REC_FILE}" > "$REC_META"
    echo "[$(date)] Starting record: Choice='$audio_choice', Target='$AUDIO_TARGET', File='$REC_FILE', Mic='$MIC_NAME', Sink='$SINK_NAME', Mon='$MON_NAME'" >> /tmp/screenrec.log

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
