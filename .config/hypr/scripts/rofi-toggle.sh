#!/bin/bash
# rofi-toggle.sh - Open / close the launcher (Super + Q)
# Apps, Files, Windows and Run modes, with a crop of the current wallpaper as the art panel.

if pgrep -x rofi >/dev/null; then
    pkill -x rofi
    exit 0
fi

# Ensure web app icons are synced for Rofi
if [ -x "$HOME/.config/hypr/scripts/sync-app-icons.sh" ]; then
    "$HOME/.config/hypr/scripts/sync-app-icons.sh" >/dev/null 2>&1 &
fi

# Art panel: a small crop of the wallpaper, rebuilt only when the wallpaper changed
ART="$HOME/.cache/wal/launcher-art.jpg"
wall=$(readlink -f "$HOME/Pictures/wallpapers/current.jpg" 2>/dev/null)
if [ -f "$wall" ] && { [ ! -f "$ART" ] || [ "$(cat "$ART.src" 2>/dev/null)" != "$wall" ] || [ "$wall" -nt "$ART" ]; }; then
    mkdir -p "$(dirname "$ART")"
    python3 "$HOME/.config/hypr/scripts/launcher-art.py" "$wall" "$ART" 2>/dev/null && echo "$wall" > "$ART.src"
fi

art_theme=""
[ -f "$ART" ] && art_theme="imagebox { background-image: url(\"$ART\", both); }"

rofi -show drun -modi "drun,filebrowser,window,run" \
    -theme "$HOME/.config/rofi/launcher.rasi" -theme-str "$art_theme"
