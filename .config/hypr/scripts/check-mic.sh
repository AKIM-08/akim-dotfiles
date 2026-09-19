#!/bin/bash
# check-mic.sh - Returns true if microphone is muted, false otherwise
if wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | grep -q MUTED; then
    echo "true"
elif command -v pamixer &>/dev/null && [ "$(pamixer --default-source --get-mute 2>/dev/null)" = "true" ]; then
    echo "true"
else
    echo "false"
fi
