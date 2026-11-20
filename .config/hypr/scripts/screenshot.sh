#!/usr/bin/env bash
# screenshot.sh - Multi-choice Screenshot and Screen Recording tool for Hyprland
# Features:
# - Full toggle support (SUPER+P opens and closes menu, SUPER+SHIFT+P captures region)
# - Clean transparent marquee selection
# - Persistent on-screen red bounding box during region video recording
# - Audio source selection: Device / System Audio, Microphone, Both, or No Audio

set -euo pipefail

# Pictures folder in the user's language (~/Images in French, ~/Bilder in German...), from
# xdg-user-dirs; ~/Pictures when it isn't set
PICTURES_DIR=$(xdg-user-dir PICTURES 2>/dev/null)
{ [ -n "$PICTURES_DIR" ] && [ "$PICTURES_DIR" != "$HOME" ]; } || PICTURES_DIR="$HOME/Pictures"
VIDEOS_DIR=$(xdg-user-dir VIDEOS 2>/dev/null)
{ [ -n "$VIDEOS_DIR" ] && [ "$VIDEOS_DIR" != "$HOME" ]; } || VIDEOS_DIR="$HOME/Videos"
DIR="${XDG_SCREENSHOTS_DIR:-$PICTURES_DIR/Screenshots}"
VID_DIR="$VIDEOS_DIR/Recordings"
mkdir -p "$DIR" "$VID_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILE="$DIR/screenshot-${TIMESTAMP}.png"
REC_FILE="$VID_DIR/recording-${TIMESTAMP}.mp4"
LOOPBACK_FILE="/tmp/wf_loopback_module.id"
MIC_VOL_FILE="/tmp/akimrec_mic_volume"
SINK_SAVE_FILE="/tmp/akimrec_default_sink"
MUTED_SINK_FILE="/tmp/akimrec_muted_sink"

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
        notify-send -e -a "Screenshot" -u low -t 2500 -h string:x-canonical-private-synchronous:screenshot \
            -i "$target_file" "$label" "Saved to $(basename "$target_file") and copied to clipboard"
    fi
}

# Capture active window geometry
get_active_window_geom() {
    if command -v hyprctl &>/dev/null; then
        hyprctl activewindow -j 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'at' in data and 'size' in data and data['size'][0] > 0 and data['size'][1] > 0:
        cls = data.get('class', '').lower()
        if 'rofi' not in cls and cls != '':
            print(f\"{data['at'][0]},{data['at'][1]} {data['size'][0]}x{data['size'][1]}\")
except Exception:
    sys.exit(1)
"
    fi
}

# 1. Selection (Region)
capture_region() {
    sleep 0.2
    local geom
    geom=$(slurp "${SLURP_ARGS[@]}") || exit 0
    grim -g "$geom" "$FILE"
    post_capture "$FILE" "Region Screenshot"
}

# 2. Entire Screen (Full)
capture_full() {
    sleep 0.35
    grim "$FILE"
    post_capture "$FILE" "Fullscreen Screenshot"
}

# 3. Active Window
capture_window() {
    # Ensure Rofi menu has finished closing and compositor fade-out animation completes
    sleep 0.35
    local geom
    geom=$(get_active_window_geom 2>/dev/null) || geom=""
    if [ -z "$geom" ]; then
        geom="${PREV_WINDOW_GEOM:-}"
    fi

    if [ -n "$geom" ]; then
        grim -g "$geom" "$FILE"
        post_capture "$FILE" "Active Window Screenshot"
    else
        capture_region
    fi
}

# 4. Select a Window (Interactive click)
capture_select_window() {
    sleep 0.2
    local geom
    if command -v hyprctl &>/dev/null; then
        geom=$(hyprctl clients -j | python3 -c "
import sys, json
try:
    clients = json.load(sys.stdin)
    boxes = [f\"{c['at'][0]},{c['at'][1]} {c['size'][0]}x{c['size'][1]}\" for c in clients if c.get('mapped', True) and 'rofi' not in c.get('class', '').lower()]
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
    sleep 0.2
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
            notify-send -e -a "Screenshot" "Tip" "Install swappy to draw arrows/text on screenshots: sudo apt install swappy" -u low
        fi
    fi
}

REC_META="/tmp/wf_rec_active.info"

# Helper: Unload any active loopback modules to prevent mic bleeding into desktop/speaker audio
# A real microphone: the default input, unless it's a "monitor" (what the speakers play)
real_mic() {
    local d
    d=$(pactl get-default-source 2>/dev/null)
    if [ -n "$d" ] && [[ "$d" != *.monitor ]]; then
        echo "$d"
        return
    fi
    pactl list short sources 2>/dev/null | awk '$2 !~ /\.monitor$/ { print $2; exit }'
}

# True when sound goes to headphones or Bluetooth (the microphone can't hear those)
output_is_headphones() {
    local def
    def=$(pactl get-default-sink 2>/dev/null)
    [[ "$def" == bluez* ]] && return 0
    pactl list sinks 2>/dev/null | awk -v d="$def" '
        /^[[:space:]]*Name:/ { cur = $2 }
        cur == d && /Active Port:/ { print tolower($0) }' | grep -qE "headphone|headset"
}

# Recording only the microphone on the laptop's speakers: the mic would hear them, so they are
# muted until the recording stops (nothing is changed with headphones or Bluetooth)
mute_speakers_for_mic() {
    command -v pactl &>/dev/null || return
    output_is_headphones && return
    local def
    def=$(pactl get-default-sink 2>/dev/null)
    [ -n "$def" ] || return
    if pactl get-sink-mute "$def" 2>/dev/null | grep -q "no"; then
        pactl set-sink-mute "$def" 1 2>/dev/null && echo "$def" > "$MUTED_SINK_FILE"
        notify-send -e -a "Screen Recorder" -u low -t 3000 "Speakers muted" \
            "So the microphone only records your voice. They come back when the recording stops." 2>/dev/null
    fi
}

cleanup_loopback() {
    # Speakers muted for a microphone recording come back
    if [ -f "$MUTED_SINK_FILE" ] && command -v pactl &>/dev/null; then
        pactl set-sink-mute "$(cat "$MUTED_SINK_FILE")" 0 2>/dev/null
        rm -f "$MUTED_SINK_FILE"
    fi
    # (Older versions changed the default output for an echo canceller: put it back)
    if [ -f "$SINK_SAVE_FILE" ] && command -v pactl &>/dev/null; then
        local orig
        orig=$(cat "$SINK_SAVE_FILE")
        if [ -n "$orig" ]; then
            pactl set-default-sink "$orig" 2>/dev/null
            pactl list short sink-inputs 2>/dev/null | awk '{print $1}' | while read -r si; do
                pactl move-sink-input "$si" "$orig" 2>/dev/null || true
            done
        fi
        rm -f "$SINK_SAVE_FILE"
    fi
    # Our own audio modules only (mix, echo canceller); never the user's other loopbacks
    if command -v pactl &>/dev/null; then
        if [ -f "$LOOPBACK_FILE" ]; then
            while read -r mod_id; do
                [ -n "$mod_id" ] && pactl unload-module "$mod_id" 2>/dev/null || true
            done < "$LOOPBACK_FILE"
        fi
        pactl list short modules 2>/dev/null | awk '/akimrec/ {print $1}' | while read -r mid; do
            pactl unload-module "$mid" 2>/dev/null || true
        done
    fi
    rm -f "$LOOPBACK_FILE"
    # The microphone volume lowered for the recording goes back to what it was
    if [ -f "$MIC_VOL_FILE" ]; then
        wpctl set-volume @DEFAULT_AUDIO_SOURCE@ "$(cat "$MIC_VOL_FILE")" 2>/dev/null || true
        rm -f "$MIC_VOL_FILE"
    fi
}

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

        if command -v notify-send &>/dev/null; then
            notify-send -a "Screen Recorder" -u low -t 4000 -h string:x-canonical-private-synchronous:screenrec \
                -i video-x-generic "Recording saved" "$(basename "${saved_file:-recording}") in $VID_DIR"
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

    local audio_choice key
    # Pill bar overlay (remembers the last choice); the Rofi list when GTK layer-shell is missing
    if python3 -c 'import gi; gi.require_version("GtkLayerShell", "0.1")' 2>/dev/null; then
        key=$(python3 "$HOME/.config/hypr/scripts/overlay_menu.py" audio 2>/dev/null | tail -1)
        case "$key" in
            sys)  audio_choice="$opt_sys" ;;
            mic)  audio_choice="$opt_mic" ;;
            both) audio_choice="$opt_both" ;;
            none) audio_choice="$opt_none" ;;
            *)    audio_choice="" ;;
        esac
    else
        audio_choice=$(printf "%s\n%s\n%s\n%s" "$opt_sys" "$opt_mic" "$opt_both" "$opt_none" | \
            rofi -dmenu -i -p "󰍬 Audio Source" -theme "$HOME/.config/rofi/screenshot.rasi" || true)
    fi

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
if wp_mic and 'output' not in wp_mic.lower() and not wp_mic.endswith('.monitor'):
    mic_target = wp_mic

wp_sink = wpctl_node('@DEFAULT_AUDIO_SINK@')
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

    # Make sure the microphone isn't muted (its volume is left as you set it)
    case "$audio_choice" in
        *"Microphone"*|*"Both"*)
            command -v wpctl &>/dev/null && wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0 2>/dev/null
            ;;
    esac

    local AUDIO_ARGS=()

    case "$audio_choice" in
        *"Device / System"*)
            AUDIO_TARGET="$MON_NAME"
            ;;
        *"Microphone"*)
            # Only your voice, at full quality: the real microphone, nothing processed. The
            # laptop speakers are muted meanwhile so the microphone can't hear them.
            MIC_NAME=$(real_mic)
            mute_speakers_for_mic
            AUDIO_TARGET="$MIC_NAME"
            ;;
        *"Both"*)
            # A silent "Recording mix" device that receives the system sound and the microphone;
            # the recorder records that mix. Nothing is played back, so you don't hear yourself.
            MIC_NAME=$(real_mic)
            if [ -n "$MIC_NAME" ] && command -v pactl &>/dev/null; then
                local ids=() id
                id=$(pactl load-module module-null-sink sink_name=akimrec_mix \
                    sink_properties=device.description=Recording-mix 2>/dev/null) && ids+=("$id")
                id=$(pactl load-module module-loopback source="$MON_NAME" sink=akimrec_mix latency_msec=60 \
                    source_dont_move=true sink_dont_move=true 2>/dev/null) && ids+=("$id")
                id=$(pactl load-module module-loopback source="$MIC_NAME" sink=akimrec_mix latency_msec=60 \
                    source_dont_move=true sink_dont_move=true 2>/dev/null) && ids+=("$id")
                printf '%s\n' "${ids[@]}" > "$LOOPBACK_FILE"
                # A new device must not become the default output
                [ -n "$SINK_NAME" ] && pactl set-default-sink "$SINK_NAME" 2>/dev/null
                AUDIO_TARGET="akimrec_mix.monitor"
            else
                AUDIO_TARGET="$MON_NAME"
            fi
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
        notify-send -e -a "Screen Recorder" -u low -t 3000 -h string:x-canonical-private-synchronous:screenrec \
            "Select the area to record" "Drag a box, or press Esc for the whole screen"
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

        python3 "$HOME/.config/hypr/scripts/record-border.py" "$gx" "$gy" "$gw" "$gh" >/dev/null 2>&1 &
    fi

    # 4. Start recording process. wf-recorder encodes on the graphics chip (VA-API) when it can,
    #    which keeps the CPU (and the fan) quiet; if that doesn't start, it encodes on the CPU.
    if [ "$RECORDER" = "wf-recorder" ]; then
        local GEOM_ARGS=() VIDEO_ARGS=()
        [ -n "$geom" ] && GEOM_ARGS=(-g "$geom")
        if [ -e /dev/dri/renderD128 ] && ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_vaapi; then
            VIDEO_ARGS=(-c h264_vaapi -d /dev/dri/renderD128)
        fi
        wf-recorder "${GEOM_ARGS[@]}" -f "$REC_FILE" "${VIDEO_ARGS[@]}" "${AUDIO_ARGS[@]}" >>/tmp/screenrec.log 2>&1 &
        if [ ${#VIDEO_ARGS[@]} -gt 0 ]; then
            sleep 1.2
            if ! pgrep -x wf-recorder >/dev/null; then
                echo "[$(date)] VA-API encoding failed, using the CPU" >> /tmp/screenrec.log
                rm -f "$REC_FILE"
                wf-recorder "${GEOM_ARGS[@]}" -f "$REC_FILE" "${AUDIO_ARGS[@]}" >>/tmp/screenrec.log 2>&1 &
            fi
        fi
    else
        if [ -n "$geom" ]; then
            wl-screenrec -g "$geom" -f "$REC_FILE" "${AUDIO_ARGS[@]}" &
        else
            wl-screenrec -f "$REC_FILE" "${AUDIO_ARGS[@]}" &
        fi
    fi

    if command -v notify-send &>/dev/null; then
        notify-send -e -a "Screen Recorder" -u low -t 3000 -h string:x-canonical-private-synchronous:screenrec -i media-record \
            "Recording" "Stop with Super + Shift + R, or Super + P → Stop recording"
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

    # Save active window geometry before Rofi takes focus
    PREV_WINDOW_GEOM=$(get_active_window_geom 2>/dev/null || true)

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
