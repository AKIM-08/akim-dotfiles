#!/bin/bash
# snmenu-toggle.sh - Power menu toggle (snmenu with sleek fallback)

set -euo pipefail

# If the Python radial menu is already running, toggle it off
if pgrep -f 'python3.*snmenu\.py' >/dev/null 2>&1; then
    pkill -f 'python3.*snmenu\.py' 2>/dev/null || true
    exit 0
fi

# If native snmenu binary is already running, toggle it off
if pgrep -x snmenu >/dev/null 2>&1; then
    pkill -x snmenu
    exit 0
fi

# If wlogout is already running, toggle it off
if pgrep -x wlogout >/dev/null 2>&1; then
    pkill -x wlogout
    exit 0
fi

# Ensure ~/.config/snmenu has the layout and style from cpmenu
mkdir -p "$HOME/.config/snmenu"
if [ -d "$HOME/.config/cpmenu" ]; then
    [ -f "$HOME/.config/cpmenu/layout" ] && ln -sf "$HOME/.config/cpmenu/layout" "$HOME/.config/snmenu/layout" 2>/dev/null || true
    [ -f "$HOME/.config/cpmenu/style.css" ] && ln -sf "$HOME/.config/cpmenu/style.css" "$HOME/.config/snmenu/style.css" 2>/dev/null || true
fi

# 1. Native snmenu binary if installed
if command -v snmenu &>/dev/null; then
    exec snmenu
fi
if [ -x "$HOME/.local/bin/snmenu" ]; then
    exec "$HOME/.local/bin/snmenu"
fi

# 2. Python GTK3/Cairo native radial menu (exact replica of SNMenu)
if [ -f "$HOME/.config/hypr/scripts/snmenu.py" ]; then
    exec python3 "$HOME/.config/hypr/scripts/snmenu.py"
fi

# 3. wlogout if installed
if command -v wlogout &>/dev/null; then
    exec wlogout -b 5
fi

# 4. Seamless Rofi power menu fallback using active wallpaper theme
chosen=$(printf "  Lock\n  Logout\n  Suspend\n  Hibernate\n  Reboot\n  Shutdown" | rofi -dmenu -i -p "Power Menu" -config "$HOME/.config/rofi/clipboard.rasi")
case "$chosen" in
    *Lock*) hyprlock ;;
    *Logout*) hyprctl dispatch exit ;;
    *Suspend*) systemctl suspend ;;
    *Hibernate*) systemctl hibernate ;;
    *Reboot*) systemctl reboot ;;
    *Shutdown*) systemctl poweroff ;;
esac
