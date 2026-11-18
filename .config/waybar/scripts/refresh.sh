#!/bin/bash
# refresh.sh - toggle the bar: stop it if it runs (Waybar or the island), otherwise start it

if pgrep -x waybar >/dev/null || pgrep -f "hypr/scripts/island\.py" >/dev/null; then
    pkill -f "waybar/scripts/dock-autohide\.py" 2>/dev/null
    pkill -f "hypr/scripts/island\.py" 2>/dev/null
    pkill -x waybar
else
    "$HOME/.config/waybar/scripts/launch.sh"
fi
