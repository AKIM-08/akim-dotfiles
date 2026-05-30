#!/bin/bash
# Launch preferred browser

if command -v firefox >/dev/null; then
    exec firefox
elif command -v brave >/dev/null; then
    exec brave
elif command -v chromium >/dev/null; then
    exec chromium
else
    notify-send "Browser" "No browser installed (firefox, brave, chromium)" -u critical
fi
