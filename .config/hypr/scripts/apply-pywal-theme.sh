#!/bin/bash
# apply-pywal-theme.sh - Regenerate UI colors from the active wallpaper via pywal16
# Usage: apply-pywal-theme.sh [path/to/wallpaper.jpg]

set -uo pipefail

WALLPAPER="${1:-$HOME/Pictures/wallpapers/current.jpg}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAL_CACHE="$HOME/.cache/wal"

link_pywal_css() {
    local dir
    for dir in waybar swaync wlogout; do
        mkdir -p "$HOME/.config/$dir"
        ln -sf "$WAL_CACHE/colors-waybar.css" "$HOME/.config/$dir/colors-waybar.css"
    done
}

reload_ui() {
    hyprctl reload 2>/dev/null || true
    pkill waybar 2>/dev/null || true
    waybar & disown || true
    if command -v swaync-client &>/dev/null; then
        swaync-client --reload-css 2>/dev/null || {
            pkill swaync 2>/dev/null || true
            swaync & disown || true
        }
    else
        pkill swaync 2>/dev/null || true
        swaync & disown || true
    fi
}

if [ ! -f "$WALLPAPER" ]; then
    notify-send "Theme" "Wallpaper not found: $WALLPAPER" -u critical 2>/dev/null || true
    exit 1
fi

mkdir -p "$WAL_CACHE"

if wal -i "$WALLPAPER" -n -q --cols16; then
    :
elif wal -i "$WALLPAPER" -n --cols16; then
    :
else
    echo "WARNING: pywal16 failed, extracting palette from image..." >&2
    python3 "$SCRIPT_DIR/pywal-fallback.py" "$WALLPAPER" || exit 1
fi

link_pywal_css
command -v pywal-discord &>/dev/null && pywal-discord -t default
reload_ui
