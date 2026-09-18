#!/bin/bash
set -euo pipefail

# Always ensure pywal colors are linked if available
if [ -f "$HOME/.cache/wal/colors-waybar.css" ]; then
    ln -sf "$HOME/.cache/wal/colors-waybar.css" "$HOME/.config/swaync/colors-waybar.css" 2>/dev/null || true
fi

python3 "$HOME/.config/swaync/patch-backlight-device.py" "$HOME/.config/swaync/config.json" 2>/dev/null || true

exec swaync "$@"
