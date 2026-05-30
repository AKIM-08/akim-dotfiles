#!/bin/bash
# Toggle clipboard history picker (Rofi + cliphist)

MARKER="${XDG_RUNTIME_DIR:-/tmp}/akim-cliphist-rofi"

if [ -f "$MARKER" ] && pgrep -x rofi >/dev/null; then
    pkill -x rofi
    rm -f "$MARKER"
    exit 0
fi

touch "$MARKER"
trap 'rm -f "$MARKER"' EXIT

sel=$(cliphist list | rofi -dmenu -i -p "Clipboard" -config ~/.config/rofi/clipboard.rasi)
[ -n "$sel" ] && printf '%s' "$sel" | cliphist decode | wl-copy
