#!/bin/bash
# switch-wallpaper.sh - Cycle through wallpapers with ultra-smooth transitions and update pywal16 theme
# Usage: switch-wallpaper.sh next|prev

WALLPAPER_DIR="$HOME/Pictures/wallpapers"
CURRENT="$WALLPAPER_DIR/current.jpg"
STATE_FILE="$HOME/.cache/wal/current_index"
APPLY_THEME="$HOME/.config/hypr/scripts/apply-pywal-theme.sh"

# Build sorted list of image files (exclude current.jpg)
mapfile -t images < <(find "$WALLPAPER_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) ! -name 'current.jpg' | sort)

if [ ${#images[@]} -eq 0 ]; then
    notify-send "Wallpaper Switcher" "No wallpapers found in $WALLPAPER_DIR" -u critical
    exit 1
fi

total=${#images[@]}

if [ -f "$STATE_FILE" ]; then
    index=$(cat "$STATE_FILE")
    if ! [[ "$index" =~ ^[0-9]+$ ]] || [ "$index" -ge "$total" ]; then
        index=0
    fi
else
    index=0
fi

case "${1:-next}" in
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

echo "$index" > "$STATE_FILE"

selected="${images[$index]}"

# Classic-mode transitions alternate (wipe, outer, wave, grow); wallfx mode ignores them
TRANSITIONS=("wipe" "outer" "wave" "grow")
TRANS_TYPE="${TRANSITIONS[$((index % ${#TRANSITIONS[@]}))]}"

# Symlinks current.jpg, plays the transition and rethemes
exec "$HOME/.config/hypr/scripts/set-wallpaper.sh" "$selected" "$TRANS_TYPE"
