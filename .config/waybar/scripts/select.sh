#!/bin/bash
WAYBAR_DIR="$HOME/.config/waybar"
STYLECSS="$WAYBAR_DIR/style.css"
CONFIG="$WAYBAR_DIR/config"
THEMES="$WAYBAR_DIR/themes"
WAL_CACHE="$HOME/.cache/wal"

apply_theme() {
    local theme="$1"
    [ -f "$THEMES/$theme/style-$theme.css" ] && cat "$THEMES/$theme/style-$theme.css" > "$STYLECSS"
    [ -f "$THEMES/$theme/config-$theme" ] && cat "$THEMES/$theme/config-$theme" > "$CONFIG"
    
    # Ensure pywal colors link is in place
    ln -sf "$WAL_CACHE/colors-waybar.css" "$WAYBAR_DIR/colors-waybar.css" 2>/dev/null || true
    
    pkill waybar && waybar &
}

# Menu options with rich Nerd Font icons and descriptions
OPTIONS="󰕮  Default       —  Classic Floating Pill Bar\n󰤄  Line          —  Minimal Edge-to-Edge Top Bar\n󰾍  Zen           —  Clean Centered Floating Island\n󰘚  Experimental  —  Dynamic Multi-Module Bar"

if command -v rofi &>/dev/null; then
    choice=$(echo -e "$OPTIONS" | rofi -dmenu -i -theme "$HOME/.config/rofi/waybar.rasi")
elif command -v wofi &>/dev/null; then
    choice=$(printf "default\nline\nzen\nexperimental" | wofi --dmenu --prompt "Select Waybar Theme")
fi

case "$choice" in
    *Default*) apply_theme default ;;
    *Line*) apply_theme line ;;
    *Zen*) apply_theme zen ;;
    *Experimental*) apply_theme experimental ;;
    default) apply_theme default ;;
    line) apply_theme line ;;
    zen) apply_theme zen ;;
    experimental) apply_theme experimental ;;
esac
