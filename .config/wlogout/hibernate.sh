#!/bin/bash
if swapon --show 2>/dev/null | grep -q .; then
    systemctl hibernate
else
    notify-send "Hibernation" "No active swap — hibernation unavailable" -u critical 2>/dev/null || true
fi
