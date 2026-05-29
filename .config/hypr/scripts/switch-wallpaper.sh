#!/bin/bash
# switch-wallpaper.sh - Cycle through wallpapers and update pywal16 theme
# Usage: switch-wallpaper.sh next|prev

WALLPAPER_DIR="$HOME/Pictures/wallpapers"
CURRENT="$WALLPAPER_DIR/current.jpg"
STATE_FILE="$HOME/.cache/wal/current_index"

# Build sorted list of image files (exclude current.jpg)
mapfile -t images < <(find "$WALLPAPER_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) ! -name 'current.jpg' | sort)

# Exit if no wallpapers found
if [ ${#images[@]} -eq 0 ]; then
    notify-send "Wallpaper Switcher" "No wallpapers found in $WALLPAPER_DIR" -u critical
    exit 1
fi

# Read current index from state file (default 0)
if [ -f "$STATE_FILE" ]; then
    index=$(cat "$STATE_FILE")
else
    index=0
fi

# Calculate new index based on direction
total=${#images[@]}
case "$1" in
    next)
        index=$(( (index + 1) % total ))
        ;;
    prev)
        index=$(( (index - 1 + total) % total ))
        ;;
    *)
        echo "Usage: $0 next|prev"
        exit 1
        ;;
esac

# Save new index
echo "$index" > "$STATE_FILE"

# Get the selected wallpaper
selected="${images[$index]}"
filename=$(basename "$selected")

# Copy selected wallpaper as current.jpg
cp "$selected" "$CURRENT"

# Update hyprpaper
hyprctl hyprpaper unload all
hyprctl hyprpaper preload "$CURRENT"
hyprctl hyprpaper wallpaper ",$CURRENT"

# Run pywal16 to regenerate color scheme from new wallpaper
wal -i "$CURRENT" -n -q --cols16

# Reload Hyprland and waybar to pick up new pywal16 colors
hyprctl reload
pkill waybar && waybar &

# Send notification
notify-send "Wallpaper Switcher" "Changed to: $filename ($((index+1))/$total)" -i "$CURRENT"
