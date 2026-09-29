#!/bin/bash
# Toggle Rofi drun launcher (open / close)

if pgrep -x rofi >/dev/null; then
    pkill -x rofi
else
    # Ensure web app icons are synced for Rofi
    if [ -x "$HOME/.config/hypr/scripts/sync-app-icons.sh" ]; then
        "$HOME/.config/hypr/scripts/sync-app-icons.sh" >/dev/null 2>&1 &
    fi
    rofi -show drun
fi
