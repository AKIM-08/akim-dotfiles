#!/usr/bin/env bash
# position.sh — Change Waybar screen location (top, bottom, left, right)
# Usage:
#   position.sh              -> Interactive menu (Rofi / Wofi)
#   position.sh <position>   -> Direct change (top | bottom | left | right)

WAYBAR_DIR="$HOME/.config/waybar"
CONFIG="$WAYBAR_DIR/config"
POS_FILE="$WAYBAR_DIR/position"

# Toggle support: If selector is already open, close it
if pgrep -f "Select Waybar Position" >/dev/null 2>&1; then
    pkill -f "Select Waybar Position" 2>/dev/null || true
    exit 0
fi

apply_position() {
    local pos="$1"
    [ -f "$CONFIG" ] || return 1

    case "$pos" in
        top|bottom|left|right) ;;
        *) echo "Invalid position: $pos (must be top, bottom, left, or right)"; return 1 ;;
    esac

    # Update position attribute in waybar config
    sed -i -E 's/"position"[[:space:]]*:[[:space:]]*"[^"]*"/"position": "'"$pos"'"/' "$CONFIG"

    # Adapt directional margins if configured
    case "$pos" in
        top)
            sed -i -E 's/"margin-top"[[:space:]]*:[[:space:]]*[0-9]+/"margin-top": 7/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-bottom"[[:space:]]*:[[:space:]]*[0-9]+/"margin-bottom": 0/' "$CONFIG" 2>/dev/null || true
            ;;
        bottom)
            sed -i -E 's/"margin-top"[[:space:]]*:[[:space:]]*[0-9]+/"margin-top": 0/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-bottom"[[:space:]]*:[[:space:]]*[0-9]+/"margin-bottom": 7/' "$CONFIG" 2>/dev/null || true
            ;;
        left)
            sed -i -E 's/"margin-left"[[:space:]]*:[[:space:]]*[0-9]+/"margin-left": 7/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-right"[[:space:]]*:[[:space:]]*[0-9]+/"margin-right": 0/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-top"[[:space:]]*:[[:space:]]*[0-9]+/"margin-top": 10/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-bottom"[[:space:]]*:[[:space:]]*[0-9]+/"margin-bottom": 10/' "$CONFIG" 2>/dev/null || true
            ;;
        right)
            sed -i -E 's/"margin-right"[[:space:]]*:[[:space:]]*[0-9]+/"margin-right": 7/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-left"[[:space:]]*:[[:space:]]*[0-9]+/"margin-left": 0/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-top"[[:space:]]*:[[:space:]]*[0-9]+/"margin-top": 10/' "$CONFIG" 2>/dev/null || true
            sed -i -E 's/"margin-bottom"[[:space:]]*:[[:space:]]*[0-9]+/"margin-bottom": 10/' "$CONFIG" 2>/dev/null || true
            ;;
    esac

    # Save preference
    echo "$pos" > "$POS_FILE"

    # Reload waybar
    pkill -x waybar 2>/dev/null || true
    sleep 0.15
    waybar &

    notify-send -h string:x-canonical-private-synchronous:sys-notify -u low \
        "Waybar" "Position updated to: $pos" 2>/dev/null || true
}

chosen="$1"

if [ -z "$chosen" ]; then
    OPTIONS="󰁝  Top     —  Top edge of screen (Default)\n󰁅  Bottom  —  Bottom edge of screen\n󰁍  Left    —  Vertical bar on left edge\n󰁔  Right   —  Vertical bar on right edge"

    if command -v rofi &>/dev/null; then
        choice=$(echo -e "$OPTIONS" | rofi -dmenu -i -p "Position" -theme "$HOME/.config/rofi/waybar.rasi") || true
    elif command -v wofi &>/dev/null; then
        choice=$(printf "Top\nBottom\nLeft\nRight" | wofi --dmenu --prompt "Select Waybar Position") || true
    fi

    [ -z "$choice" ] && exit 0

    case "$choice" in
        *Top*|top) chosen="top" ;;
        *Bottom*|bottom) chosen="bottom" ;;
        *Left*|left) chosen="left" ;;
        *Right*|right) chosen="right" ;;
        *) exit 0 ;;
    esac
fi

apply_position "$chosen"
