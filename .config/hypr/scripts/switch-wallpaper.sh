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
filename=$(basename "$selected")

# Symlink avoids re-encoding JPEG and keeps 100% original full image quality
ln -sf "$selected" "$CURRENT"
real_current=$(readlink -f "$CURRENT")

# Initialise le démon awww s'il n'est pas lancé
if ! pgrep -x awww-daemon >/dev/null; then
    awww-daemon & disown
    sleep 0.5
fi

# Transitions élégantes alternées (wipe, outer, wave, grow)
TRANSITIONS=("wipe" "outer" "wave" "grow")
TRANS_TYPE="${TRANSITIONS[$((index % ${#TRANSITIONS[@]}))]}"

# Applique l'image originale avec rendu GPU matériel HD (Filtre Lanczos3 pour netteté maximale)
awww img "$real_current" \
    --transition-type "$TRANS_TYPE" \
    --transition-angle 30 \
    --transition-step 90 \
    --transition-fps 60 \
    --filter Lanczos3 \
    --resize crop


"$APPLY_THEME" "$real_current"

notify-send "Wallpaper Switcher" "Changed to: $filename ($((index+1))/$total)" -i "$real_current"
