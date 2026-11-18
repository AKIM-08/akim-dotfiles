#!/usr/bin/env bash
# launch.sh - (re)start the bar for the saved Waybar theme
#
#   most themes   Waybar
#   dock          Waybar + dock-autohide.py (shows the dock when the pointer touches its edge)
#   island        ~/.config/hypr/scripts/island.py instead of Waybar
#
# Used at login (hyprland.hl), by select.sh after a theme change and by refresh.sh.

WAYBAR_DIR="$HOME/.config/waybar"
ISLAND="$HOME/.config/hypr/scripts/island.py"
AUTOHIDE="$WAYBAR_DIR/scripts/dock-autohide.py"

prog=$(python3 "$WAYBAR_DIR/scripts/layout.py" --program 2>/dev/null)
[ -n "$prog" ] || prog=waybar

pkill -f "waybar/scripts/dock-autohide\.py" 2>/dev/null
pkill -f "hypr/scripts/island\.py" 2>/dev/null
pkill -x waybar 2>/dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -x waybar >/dev/null || pgrep -f "hypr/scripts/island\.py" >/dev/null || break
    sleep 0.05
done
# The island hides SwayNC's own popups while it runs; make sure they come back without it
[ "$prog" = island ] || swaync-client --inhibitor-remove island >/dev/null 2>&1

case "$prog" in
    island)
        setsid -f python3 "$ISLAND" >/dev/null 2>&1 ;;
    dock)
        setsid -f waybar >/dev/null 2>&1
        setsid -f python3 "$AUTOHIDE" >/dev/null 2>&1 ;;
    *)
        setsid -f waybar >/dev/null 2>&1 ;;
esac
exit 0
