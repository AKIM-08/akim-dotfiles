#!/bin/bash

set -euo pipefail

python3 "$HOME/.config/swaync/patch-backlight-device.py" "$HOME/.config/swaync/config.json" 2>/dev/null || true

exec swaync
