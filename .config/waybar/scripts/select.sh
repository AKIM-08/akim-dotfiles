#!/usr/bin/env bash
# select.sh — Interactive Waybar Theme / Layout & Position Selector with toggle support

# Toggle support: If Waybar selector is already running, close it and exit
if pgrep -f "waybar.rasi" >/dev/null 2>&1; then
    pkill -f "waybar.rasi" 2>/dev/null || true
    exit 0
fi

if pgrep -f "Select Waybar" >/dev/null 2>&1; then
    pkill -f "Select Waybar" 2>/dev/null || true
    exit 0
fi

WAYBAR_DIR="$HOME/.config/waybar"
STYLECSS="$WAYBAR_DIR/style.css"
CONFIG="$WAYBAR_DIR/config"
THEMES="$WAYBAR_DIR/themes"
WAL_CACHE="$HOME/.cache/wal"
POS_FILE="$WAYBAR_DIR/position"
SCRIPTS_DIR="$WAYBAR_DIR/scripts"

# Read currently saved position (fallback: check current config or default to top)
get_current_position() {
    if [ -f "$POS_FILE" ]; then
        cat "$POS_FILE" 2>/dev/null | tr -d '[:space:]'
    elif [ -f "$CONFIG" ]; then
        grep -o '"position"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG" 2>/dev/null | head -1 | cut -d'"' -f4
    else
        echo "top"
    fi
}

ask_position() {
    local default_pos
    default_pos=$(get_current_position)
    [ -z "$default_pos" ] && default_pos="top"

    local pos_options="󰁝  Top     —  Top edge of screen (Default)\n󰁅  Bottom  —  Bottom edge of screen\n󰁍  Left    —  Vertical bar on left edge\n󰁔  Right   —  Vertical bar on right edge"
    local pos_choice=""

    if command -v rofi &>/dev/null; then
        pos_choice=$(echo -e "$pos_options" | rofi -dmenu -i -p "Position" -theme "$HOME/.config/rofi/waybar.rasi") || true
    elif command -v wofi &>/dev/null; then
        pos_choice=$(printf "Top\nBottom\nLeft\nRight" | wofi --dmenu --prompt "Select Waybar Position") || true
    fi

    case "$pos_choice" in
        *Top*|top) echo "top" ;;
        *Bottom*|bottom) echo "bottom" ;;
        *Left*|left) echo "left" ;;
        *Right*|right) echo "right" ;;
        *) echo "$default_pos" ;;
    esac
}

apply_theme_and_position() {
    local theme="$1"
    local pos="$2"

    if [ -z "$pos" ]; then
        pos=$(ask_position)
    fi

    [ -f "$THEMES/$theme/style-$theme.css" ] && cat "$THEMES/$theme/style-$theme.css" > "$STYLECSS"
    [ -f "$THEMES/$theme/config-$theme" ] && cat "$THEMES/$theme/config-$theme" > "$CONFIG"

    # Ensure pywal colors link is in place
    ln -sf "$WAL_CACHE/colors-waybar.css" "$WAYBAR_DIR/colors-waybar.css" 2>/dev/null || true

    # Apply requested position
    if [ -x "$SCRIPTS_DIR/position.sh" ]; then
        bash "$SCRIPTS_DIR/position.sh" "$pos"
    else
        sed -i -E 's/"position"[[:space:]]*:[[:space:]]*"[^"]*"/"position": "'"$pos"'"/' "$CONFIG" 2>/dev/null || true
        echo "$pos" > "$POS_FILE"
        pkill -x waybar 2>/dev/null || true
        sleep 0.15
        waybar &
    fi
}

# If arguments were provided directly on command line
if [ -n "$1" ]; then
    case "$1" in
        --position|-p)
            if [ -n "$2" ]; then
                bash "$SCRIPTS_DIR/position.sh" "$2"
            else
                bash "$SCRIPTS_DIR/position.sh"
            fi
            exit 0
            ;;
        default|line|zen|experimental|capsule)
            apply_theme_and_position "$1" "$2"
            exit 0
            ;;
    esac
fi

# Interactive Menu with Rich Nerd Font Icons
OPTIONS="󰕮  Default       —  Classic Floating Pill Bar\n󰤄  Line          —  Minimal Edge-to-Edge Bar\n󰾍  Zen           —  Clean Centered Floating Island\n󰘚  Experimental  —  Dynamic Multi-Module Bar\n󰍹  Capsule       —  Modular Floating Capsule Islands\n󰹑  Position Only —  Change Screen Edge (Top/Bottom/Left/Right)"

choice=""
if command -v rofi &>/dev/null; then
    choice=$(echo -e "$OPTIONS" | rofi -dmenu -i -p "Theme" -theme "$HOME/.config/rofi/waybar.rasi") || true
elif command -v wofi &>/dev/null; then
    choice=$(printf "default\nline\nzen\nexperimental\ncapsule\nposition" | wofi --dmenu --prompt "Select Waybar Theme") || true
fi

[ -z "$choice" ] && exit 0

case "$choice" in
    *Position*|position)
        bash "$SCRIPTS_DIR/position.sh"
        ;;
    *Default*|default)
        apply_theme_and_position default
        ;;
    *Line*|line)
        apply_theme_and_position line
        ;;
    *Zen*|zen)
        apply_theme_and_position zen
        ;;
    *Experimental*|experimental)
        apply_theme_and_position experimental
        ;;
    *Capsule*|capsule)
        apply_theme_and_position capsule
        ;;
esac
