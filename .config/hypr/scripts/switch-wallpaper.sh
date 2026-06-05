#!/bin/bash
# switch-wallpaper.sh - Cycle through wallpapers and update pywal16 theme
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

if [ -f "$STATE_FILE" ]; then
    index=$(cat "$STATE_FILE")
    # Valider l'index : doit être un entier dans les bornes du tableau
    if ! [[ "$index" =~ ^[0-9]+$ ]] || [ "$index" -ge "$total" ]; then
        index=0
    fi
else
    index=0
fi

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

echo "$index" > "$STATE_FILE"

selected="${images[$index]}"
filename=$(basename "$selected")

# Symlink avoids re-encoding JPEG and keeps full image quality
ln -sf "$selected" "$CURRENT"
real_current=$(readlink -f "$CURRENT")

# Initialise le démon awww s'il n'est pas lancé
if ! pgrep -x awww-daemon >/dev/null; then
    awww-daemon & disown
    sleep 0.5
fi

# Applique l'image avec une transition élégante et un redimensionnement de haute qualité
awww img "$real_current" \
    --transition-type wipe \
    --transition-angle 30 \
    --transition-step 90 \
    --transition-fps 60 \
    --resize crop

"$APPLY_THEME" "$real_current"

notify-send "Wallpaper Switcher" "Changed to: $filename ($((index+1))/$total)" -i "$real_current"
