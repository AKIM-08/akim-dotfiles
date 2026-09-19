#!/bin/bash
# check-mute.sh - Returns true if audio sink is muted, false otherwise
if wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null | grep -q MUTED; then
    echo "true"
elif command -v pamixer &>/dev/null && [ "$(pamixer --get-mute 2>/dev/null)" = "true" ]; then
    echo "true"
else
    echo "false"
fi
