#!/bin/bash
set -euo pipefail

# Ensure pywal colors are present in swaync config dir
if [ -f "$HOME/.cache/wal/colors-waybar.css" ]; then
    cp "$HOME/.cache/wal/colors-waybar.css" "$HOME/.config/swaync/colors-waybar.css" 2>/dev/null || true
fi

python3 "$HOME/.config/swaync/patch-backlight-device.py" "$HOME/.config/swaync/config.json" 2>/dev/null || true

exec swaync -s "$HOME/.config/swaync/style.css" -c "$HOME/.config/swaync/config.json" "$@"
