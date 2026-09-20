#!/bin/bash
# volume-mute.sh - Toggle master volume mute across PipeWire and PulseAudio

if command -v wpctl &>/dev/null; then
    wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
elif command -v pamixer &>/dev/null; then
    pamixer -t
elif command -v pactl &>/dev/null; then
    pactl set-sink-mute @DEFAULT_SINK@ toggle
fi

# Refresh SwayNC button states
(swaync-client -R 2>/dev/null &)
