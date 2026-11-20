#!/bin/bash
# rofi-wallpaper.sh - Interactive Rofi/Wofi Wallpaper Picker with preview icons & toggle support

# Toggle: Si le sélecteur Rofi/Wofi/QML est déjà ouvert, appuyer à nouveau sur SUPER+W le ferme immédiatement
if pgrep -f "wallpaper-picker\.py" >/dev/null || pgrep -x rofi >/dev/null || pgrep -x wofi >/dev/null; then
    pkill -f "wallpaper-picker\.py" 2>/dev/null || true
    pkill -x rofi 2>/dev/null || pkill -x wofi 2>/dev/null || true
    exit 0
fi

# Pictures folder in the user's language (~/Images in French, ~/Bilder in German...), from
# xdg-user-dirs; ~/Pictures when it isn't set
PICTURES_DIR=$(xdg-user-dir PICTURES 2>/dev/null)
{ [ -n "$PICTURES_DIR" ] && [ "$PICTURES_DIR" != "$HOME" ]; } || PICTURES_DIR="$HOME/Pictures"
WALLPAPER_DIR="$PICTURES_DIR/wallpapers"
CURRENT="$WALLPAPER_DIR/current.jpg"
STATE_FILE="$HOME/.cache/wal/current_index"
APPLY_THEME="$HOME/.config/hypr/scripts/apply-pywal-theme.sh"

mkdir -p "$WALLPAPER_DIR" "$HOME/.cache/wal"

mapfile -t images < <(find "$WALLPAPER_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) ! -name 'current.jpg' | sort)

if [ ${#images[@]} -eq 0 ]; then
    notify-send "Wallpaper Picker" "No wallpapers found in $WALLPAPER_DIR" -u critical
    exit 1
fi

options=""
for img in "${images[@]}"; do
    filename=$(basename "$img")
    options+="${filename}\x00icon\x1f${img}\n"
done

PICKER="$HOME/.config/hypr/scripts/wallpaper-picker.py"
selected_file=""

# Carousel picker (PyQt6); falls back to a Rofi/Wofi list when PyQt6 is missing
if python3 -c 'import PyQt6.QtWidgets' 2>/dev/null; then
    selected_file=$(python3 "$PICKER" 2>/dev/null | tail -1)
elif command -v rofi &>/dev/null; then
    selected_name=$(echo -e -n "$options" | rofi -dmenu -i -theme "$HOME/.config/rofi/wallpaper.rasi")
    [ -n "$selected_name" ] && selected_file="$WALLPAPER_DIR/$selected_name"
elif command -v wofi &>/dev/null; then
    selected_name=$(echo -e -n "$options" | wofi --dmenu --prompt "Select Wallpaper")
    [ -n "$selected_name" ] && selected_file="$WALLPAPER_DIR/$selected_name"
fi

if [ -z "$selected_file" ] || [ ! -f "$selected_file" ]; then
    exit 0
fi

for i in "${!images[@]}"; do
    if [ "${images[$i]}" = "$selected_file" ]; then
        echo "$i" > "$STATE_FILE"
        break
    fi
done

# Symlinks current.jpg, plays the transition (wallfx or awww "outer") and rethemes
exec "$HOME/.config/hypr/scripts/set-wallpaper.sh" "$selected_file" outer

