#!/usr/bin/env bash
# lockinfo.sh <what> - Text for the lock screen labels (hyprlock cmd[...] labels).
#
#   song      "♫ Title · Artist" of what is playing (empty when nothing plays)
#   status    "Wi-Fi  ·  battery  ·  keyboard layout"
#   date      e.g. "Wednesday 18 November"
#   datebat   e.g. "Wed 18 Nov · 88% battery"
#   greeting  "Welcome back, <first name>"
#   caps      "Caps Lock is on" or nothing

battery() {
    local b
    for b in /sys/class/power_supply/BAT*; do
        [ -r "$b/capacity" ] && { cat "$b/capacity"; return; }
    done
}

case "${1:-}" in
    song)
        command -v playerctl >/dev/null || exit 0
        [ "$(playerctl status 2>/dev/null)" = "Playing" ] || exit 0
        playerctl metadata --format '♫  {{title}}  ·  {{artist}}' 2>/dev/null | cut -c1-70
        ;;
    status)
        parts=()
        ssid=$(nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | awk -F: '$1=="yes" { sub(/^yes:/, ""); print; exit }')
        [ -n "$ssid" ] && parts+=("󰤨  $ssid")
        bat=$(battery)
        [ -n "$bat" ] && parts+=("󰁹  $bat%")
        layout=$(hyprctl devices 2>/dev/null | awk '/active keymap/ { $1=$2=""; sub(/^ +/, ""); print; exit }')
        [ -n "$layout" ] && parts+=("󰌌  $layout")
        out=""
        for p in "${parts[@]}"; do out+="${out:+     }$p"; done
        echo "$out"
        ;;
    date)
        date +"%A %d %B"
        ;;
    datebat)
        bat=$(battery)
        echo "$(date +"%a %d %b")${bat:+  ·  $bat% battery}"
        ;;
    greeting)
        name=$(getent passwd "$USER" | cut -d: -f5 | cut -d, -f1)
        name="${name:-$USER}"
        echo "Welcome back, ${name%% *}"
        ;;
    caps)
        for led in /sys/class/leds/*capslock*/brightness; do
            [ -r "$led" ] && [ "$(cat "$led")" != 0 ] && { echo "Caps Lock is on"; exit 0; }
        done
        ;;
esac
