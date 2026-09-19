#!/bin/bash
# detect-backlight.sh - Auto-detect active backlight device and update SwayNC config

CONFIG="$HOME/.config/swaync/config.json"
[ -f "$CONFIG" ] || exit 0

DEV=""
# 1. Try brightnessctl output
if command -v brightnessctl &>/dev/null; then
    DEV=$(brightnessctl -l -c backlight -m 2>/dev/null | head -n1 | cut -d, -f1)
fi

# 2. Try /sys/class/backlight
if [ -z "$DEV" ]; then
    for p in /sys/class/backlight/*; do
        if [ -d "$p" ]; then
            DEV=$(basename "$p")
            break
        fi
    done
fi

[ -z "$DEV" ] && DEV="intel_backlight"

python3 -c "
import json, sys
p = '$CONFIG'
try:
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    w = data.setdefault('widget-config', {}).setdefault('backlight', {})
    w['device'] = '$DEV'
    w['subsystem'] = 'backlight'
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write('\n')
except Exception:
    pass
" 2>/dev/null || true
