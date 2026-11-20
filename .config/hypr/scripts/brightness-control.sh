#!/bin/bash
# brightness-control.sh - Adjust screen backlight and show the level (pop-up, or a notification)

# Pop-up from desktop-extras.py when it runs (and the island isn't the bar: it shows levels
# itself from the notification); a short notification otherwise
osd() {
    local fifo="${XDG_RUNTIME_DIR:-/tmp}/desktop-osd.fifo"
    [ -p "$fifo" ] || return 1
    pgrep -f "hypr/scripts/island\.py" >/dev/null 2>&1 && return 1
    timeout 0.3 sh -c 'echo "$1" > "$2"' _ "$*" "$fifo" 2>/dev/null
}

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

osd brightness "$percent" && exit 0
notify-send -e -h string:x-canonical-private-synchronous:sys-notify -h int:value:"$percent" -u low "Brightness" "${percent}% 󰃟"
