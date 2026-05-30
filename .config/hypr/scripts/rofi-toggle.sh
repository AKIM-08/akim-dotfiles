#!/bin/bash
# Toggle Rofi drun launcher (open / close)

if pgrep -x rofi >/dev/null; then
    pkill -x rofi
else
    rofi -show drun
fi
