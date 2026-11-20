#!/usr/bin/env bash
# overview.sh [overview|overview-back|overview-release] - Alt + Tab window overview.
# desktop-extras.py shows it at once (it is already running); otherwise overview.py starts on its own.
fifo="${XDG_RUNTIME_DIR:-/tmp}/desktop-osd.fifo"
what="${1:-overview}"
if [ -p "$fifo" ] && pgrep -f "hypr/scripts/desktop-extras\.py" >/dev/null 2>&1; then
    timeout 0.3 sh -c 'echo "$1" > "$2"' _ "$what" "$fifo" 2>/dev/null && exit 0
fi
[ "$what" = overview-release ] && exit 0
pgrep -f "hypr/scripts/overview\.py" >/dev/null 2>&1 && exit 0
exec python3 "$HOME/.config/hypr/scripts/overview.py"
