#!/bin/bash
# rofi-wallpaper.sh - Interactive Rofi/Wofi Wallpaper Picker with preview icons

WALLPAPER_DIR="$HOME/Pictures/wallpapers"
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

if command -v rofi &>/dev/null; then
    selected_name=$(echo -e -n "$options" | rofi -dmenu -i -p "󰸉 Select Wallpaper" -theme-str 'window {width: 480px;} listview {lines: 9;}')
elif command -v wofi &>/dev/null; then
    selected_name=$(echo -e -n "$options" | wofi --dmenu --prompt "Select Wallpaper")
else
    selected_name=""
fi

if [ -z "$selected_name" ]; then
    exit 0
fi

selected_file="$WALLPAPER_DIR/$selected_name"

if [ ! -f "$selected_file" ]; then
    exit 1
fi

for i in "${!images[@]}"; do
    if [ "${images[$i]}" = "$selected_file" ]; then
        echo "$i" > "$STATE_FILE"
        break
    fi
done

ln -sf "$selected_file" "$CURRENT"
real_current=$(readlink -f "$CURRENT")

if ! pgrep -x awww-daemon >/dev/null; then
    awww-daemon & disown
    sleep 0.5
fi

awww img "$real_current" \
    --transition-type outer \
    --transition-angle 30 \
    --transition-step 90 \
    --transition-fps 60 \
    --resize crop

"$APPLY_THEME" "$real_current"
