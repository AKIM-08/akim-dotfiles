#!/bin/bash
WAYBAR_DIR="$HOME/.config/waybar"
STYLECSS="$WAYBAR_DIR/style.css"
CONFIG="$WAYBAR_DIR/config"
THEMES="$WAYBAR_DIR/themes"

apply_theme() {
    local theme="$1"
    cat "$THEMES/$theme/style-$theme.css" > "$STYLECSS"
    cat "$THEMES/$theme/config-$theme" > "$CONFIG"
    pkill waybar && waybar &
}

choice=$(printf "default\nline\nzen\nexperimental" | wofi \
    -c ~/.config/wofi/waybar \
    -s ~/.config/wofi/style-waybar.css \
    --show dmenu \
    --prompt "  Select Waybar Theme" \
    -n)

case "$choice" in
    default) apply_theme default ;;
    line) apply_theme line ;;
    zen) apply_theme zen ;;
    experimental) apply_theme experimental ;;
esac
