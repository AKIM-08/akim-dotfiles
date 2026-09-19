#!/bin/bash
# mic-mute.sh - Toggle microphone source mute across PipeWire and PulseAudio

if command -v wpctl &>/dev/null; then
    wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle
elif command -v pamixer &>/dev/null; then
    pamixer --default-source -t
elif command -v pactl &>/dev/null; then
    pactl set-source-mute @DEFAULT_SOURCE@ toggle
fi
