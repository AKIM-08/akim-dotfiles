#!/bin/bash
set -euo pipefail

# Ensure pywal colors are present in swaync config dir
if [ -f "$HOME/.cache/wal/colors-waybar.css" ]; then
    cp "$HOME/.cache/wal/colors-waybar.css" "$HOME/.config/swaync/colors-waybar.css" 2>/dev/null || true
fi

# Detect active backlight device and patch config.json
if [ -f "$HOME/.config/hypr/scripts/detect-backlight.sh" ]; then
    bash "$HOME/.config/hypr/scripts/detect-backlight.sh" 2>/dev/null || true
fi

exec swaync -s "$HOME/.config/swaync/style.css" -c "$HOME/.config/swaync/config.json" "$@"
