#!/bin/bash
# screenshot.sh - Capture screen and save to ~/Pictures/Screenshots/
# Usage: screenshot.sh [region|full]

set -euo pipefail

MODE="${1:-region}"
DIR="${XDG_SCREENSHOTS_DIR:-$HOME/Pictures/Screenshots}"
mkdir -p "$DIR"

FILE="$DIR/screenshot-$(date +%Y%m%d-%H%M%S).png"

case "$MODE" in
    region)
        GEOM=$(slurp -d) || exit 0
        grim -g "$GEOM" "$FILE"
        ;;
    full)
        grim "$FILE"
        ;;
    *)
        echo "Usage: $0 [region|full]" >&2
        exit 1
        ;;
esac

if command -v wl-copy &>/dev/null; then
    wl-copy < "$FILE"
fi

if command -v notify-send &>/dev/null; then
    notify-send "Screenshot" "Saved to $(basename "$FILE")" -i "$FILE"
fi
