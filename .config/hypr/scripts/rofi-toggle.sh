#!/bin/bash
# rofi-toggle.sh - Open / close the launcher (Super + Q)
# Apps, Files, Windows and Run modes, with a crop of the current wallpaper as the art panel.

if pgrep -x rofi >/dev/null; then
    pkill -x rofi
    exit 0
fi

# Ensure web app icons are synced for Rofi
if [ -x "$HOME/.config/hypr/scripts/sync-app-icons.sh" ]; then
    "$HOME/.config/hypr/scripts/sync-app-icons.sh" >/dev/null 2>&1 &
fi

# Art panel: a small crop of the wallpaper, rebuilt only when the wallpaper changed
ART="$HOME/.cache/wal/launcher-art.jpg"
ART_VERSION=2      # bump when launcher-art.py changes the crop
pics=$(xdg-user-dir PICTURES 2>/dev/null); { [ -n "$pics" ] && [ "$pics" != "$HOME" ]; } || pics="$HOME/Pictures"
wall=$(readlink -f "$pics/wallpapers/current.jpg" 2>/dev/null)
if [ -f "$wall" ] && { [ ! -f "$ART" ] || [ "$(cat "$ART.src" 2>/dev/null)" != "$ART_VERSION $wall" ] || [ "$wall" -nt "$ART" ]; }; then
    mkdir -p "$(dirname "$ART")"
    python3 "$HOME/.config/hypr/scripts/launcher-art.py" "$wall" "$ART" 2>/dev/null && echo "$ART_VERSION $wall" > "$ART.src"
fi

art_theme=""
[ -f "$ART" ] && art_theme="imagebox { background-image: url(\"$ART\", height); }"

# Keys:
#   Tab / Shift+Tab    next / previous mode (Apps, Files, Windows, Run); Shift+Right/Left too
#   Enter              launch, or go into a folder (Files)
#   Ctrl+Enter         open the selected folder in the file manager (Files, via kb-custom-1)
keys=(
    -kb-row-tab ""
    -kb-mode-next "Tab,Shift+Right,Control+Tab"
    -kb-mode-previous "ISO_Left_Tab,Shift+Left,Control+ISO_Left_Tab"
    -kb-accept-custom ""
    -kb-custom-1 "Control+Return"
)
# Newer Rofi also binds Tab/Shift+Tab to element-next/prev; free them (older Rofi lacks
# these options and would reject them, so only pass them when they exist)
if rofi -dump-config 2>/dev/null | grep -q 'kb-element-next'; then
    keys+=(-kb-element-next "" -kb-element-prev "")
fi

# Files is our own script mode (Rofi's file browser can't open a folder without entering it).
# Rofi 1.7.5 ignores -display-<name> for script modes, so the mode is named after its icon.
FILES_ICON="󰉋"
rofi -show drun -modi "drun,${FILES_ICON}:$HOME/.config/hypr/scripts/rofi-files.sh,window,run" \
    "${keys[@]}" \
    -theme "$HOME/.config/rofi/launcher.rasi" -theme-str "$art_theme"
