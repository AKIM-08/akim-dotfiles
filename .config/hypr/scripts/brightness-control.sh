#!/bin/bash
# brightness-control.sh - Adjust screen backlight and display OSD in SwayNC

action="${1:-}"

case "$action" in
    up)
        brightnessctl s 5%+ >/dev/null 2>&1 || true
        ;;
    down)
        brightnessctl s 5%- >/dev/null 2>&1 || true
        ;;
esac

# Get current brightness percentage
percent=$(brightnessctl -m 2>/dev/null | cut -d, -f4 | tr -d '%' || echo 50)

notify-send -h string:x-canonical-private-synchronous:sys-notify -h int:value:"$percent" -u low "Brightness" "${percent}% 󰃟"

# Refresh SwayNC widgets (backlight slider) in real time
(swaync-client -R 2>/dev/null &)
