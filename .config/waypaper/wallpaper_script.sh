#!/bin/bash
wal -i "$1" --cols16 lighten
command -v pywal-discord >/dev/null && pywal-discord -t default
hyprctl reload
pkill waybar && waybar &
