#!/bin/bash
pkill -x swaync 2>/dev/null || true
while pgrep -x swaync >/dev/null; do sleep 0.1; done
"$HOME/.config/swaync/start.sh" &
