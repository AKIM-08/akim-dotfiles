#!/usr/bin/env bash
# nightlight.sh - Warm the screen color temperature (blue light filter)
#
#   nightlight.sh <kelvin>    e.g. 4500 (soft), 3500 (warm), 2700 (very warm)
#   nightlight.sh off
#   nightlight.sh restore     re-apply the saved choice (run at login)
#   nightlight.sh status      print the saved choice ("off" or a temperature)
#   nightlight.sh toggle      off <-> the last temperature used (control-center tile)
#   nightlight.sh is-on       print true / false
#
# Uses hyprsunset if installed, otherwise gammastep, otherwise wlsunset. The tool keeps
# running while the filter is on; turning it off stops it and the colors return to normal.

STATE="$HOME/.config/hypr/nightlight"

stop_all() {
    pkill -x hyprsunset 2>/dev/null
    pkill -x gammastep 2>/dev/null
    pkill -x wlsunset 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        pgrep -x hyprsunset >/dev/null || pgrep -x gammastep >/dev/null || pgrep -x wlsunset >/dev/null || break
        sleep 0.05
    done
}

start() {   # start <kelvin>
    local k="$1"
    if command -v hyprsunset >/dev/null 2>&1; then
        setsid -f hyprsunset -t "$k" >/dev/null 2>&1
    elif command -v gammastep >/dev/null 2>&1; then
        setsid -f gammastep -O "$k" -P >/dev/null 2>&1
    elif command -v wlsunset >/dev/null 2>&1; then
        setsid -f wlsunset -T "$((k + 1))" -t "$k" >/dev/null 2>&1
    else
        notify-send -u critical "Night light" "Install gammastep (sudo apt install gammastep) or hyprsunset" 2>/dev/null
        return 1
    fi
}

case "${1:-status}" in
    off)
        stop_all
        echo off > "$STATE"
        ;;
    restore)
        k=$(cat "$STATE" 2>/dev/null)
        if [[ "$k" =~ ^[0-9]+$ ]]; then stop_all; start "$k"; fi
        ;;
    status)
        cat "$STATE" 2>/dev/null || echo off
        ;;
    is-on)     # "true"/"false" for the control-center tile
        k=$(cat "$STATE" 2>/dev/null)
        [[ "$k" =~ ^[0-9]+$ ]] && echo true || echo false
        ;;
    toggle)    # off <-> the last temperature used (3500K the first time)
        k=$(cat "$STATE" 2>/dev/null)
        if [[ "$k" =~ ^[0-9]+$ ]]; then
            echo "$k" > "$STATE.last"
            stop_all
            echo off > "$STATE"
        else
            last=$(cat "$STATE.last" 2>/dev/null)
            [[ "$last" =~ ^[0-9]+$ ]] || last=3500
            stop_all
            start "$last" && echo "$last" > "$STATE"
        fi
        ;;
    *)
        if ! [[ "$1" =~ ^[0-9]+$ ]] || [ "$1" -lt 1000 ] || [ "$1" -gt 6500 ]; then
            echo "Usage: $0 <1000-6500 kelvin> | off | restore | status" >&2
            exit 2
        fi
        stop_all
        start "$1" && echo "$1" > "$STATE"
        ;;
esac
