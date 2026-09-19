#!/bin/bash
# volume-control.sh - Adjust volume and display OSD notification in SwayNC

action="${1:-}"

case "$action" in
    up)
        if command -v wpctl &>/dev/null; then
            wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+
        elif command -v pamixer &>/dev/null; then
            pamixer -i 5
        fi
        ;;
    down)
        if command -v wpctl &>/dev/null; then
            wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-
        elif command -v pamixer &>/dev/null; then
            pamixer -d 5
        fi
        ;;
    mute)
        if command -v wpctl &>/dev/null; then
            wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
        elif command -v pamixer &>/dev/null; then
            pamixer -t
        fi
        ;;
    mic-mute)
        if command -v wpctl &>/dev/null; then
            wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle
        elif command -v pamixer &>/dev/null; then
            pamixer --default-source -t
        fi
        ;;
esac

# Get current volume and mute state
is_muted=false
vol=50

if command -v wpctl &>/dev/null; then
    status=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null || true)
    if [[ "$status" =~ \[MUTED\] ]]; then
        is_muted=true
    fi
    raw_vol=$(echo "$status" | awk '{print $2}')
    vol=$(awk "BEGIN {print int($raw_vol * 100)}")
elif command -v pamixer &>/dev/null; then
    vol=$(pamixer --get-volume 2>/dev/null || echo 50)
    if [ "$(pamixer --get-mute 2>/dev/null)" = "true" ]; then
        is_muted=true
    fi
fi

if [ "$action" = "mic-mute" ]; then
    mic_status=$(wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null || true)
    if [[ "$mic_status" =~ \[MUTED\] ]]; then
        notify-send -h string:x-canonical-private-synchronous:sys-notify -u low "Microphone" "Muted 󰍭"
    else
        notify-send -h string:x-canonical-private-synchronous:sys-notify -u low "Microphone" "Active 󰍬"
    fi
    exit 0
fi

if [ "$is_muted" = "true" ]; then
    notify-send -h string:x-canonical-private-synchronous:sys-notify -h int:value:0 -u low "Volume" "Muted (Sourdine) 󰝟"
else
    notify-send -h string:x-canonical-private-synchronous:sys-notify -h int:value:"$vol" -u low "Volume" "${vol}% 󰕾"
fi
