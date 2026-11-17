#!/usr/bin/env bash
# select.sh - Waybar theme and position selector
#
#   select.sh                     open the menu (themes + "Position" submenu)
#   select.sh <theme>             apply a theme, keep the position
#   select.sh --position <edge>   move the bar: top, bottom, left, right
#
# The live config is built by layout.py from themes/modules.json + the theme's files.

WAYBAR_DIR="$HOME/.config/waybar"
LAYOUT="$WAYBAR_DIR/scripts/layout.py"
ROFI_THEME="$HOME/.config/rofi/waybar.rasi"
WAL_CACHE="$HOME/.cache/wal"

# Toggle: pressing the shortcut again closes the menu
if pgrep -f "rofi.*waybar\.rasi" >/dev/null 2>&1; then
    pkill -f "rofi.*waybar\.rasi" 2>/dev/null || true
    exit 0
fi

restart_waybar() {
    # Pywal colors must be a regular file next to style.css (apply-pywal-theme.sh updates it in place)
    if [ -f "$WAL_CACHE/colors-waybar.css" ]; then
        rm -f "$WAYBAR_DIR/colors-waybar.css"
        cat "$WAL_CACHE/colors-waybar.css" > "$WAYBAR_DIR/colors-waybar.css"
    fi
    pkill -x waybar 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do pgrep -x waybar >/dev/null || break; sleep 0.05; done
    waybar >/dev/null 2>&1 &
    disown
}

apply() {   # arguments are passed through to layout.py
    if ! python3 "$LAYOUT" "$@"; then
        notify-send -u critical "Waybar" "Could not apply: $*" 2>/dev/null
        return 1
    fi
    restart_waybar
}

case "${1:-}" in
    --position)
        apply --position "${2:-top}"; exit $? ;;
    "") ;;
    *)
        apply --theme "$1"; exit $? ;;
esac

read -r cur_theme cur_pos < <(python3 "$LAYOUT" --get 2>/dev/null)

THEMES=(default line zen experimental capsule)
LABELS=(
    "󰕮  Default       —  Three floating islands"
    "󰤄  Line          —  Thin edge-to-edge strip"
    "󰾍  Zen           —  One island, drawer on hover"
    "󰘚  Experimental  —  Color bars, media, load"
    "󰍹  Capsule       —  Floating capsules"
    "󰁌  Position      —  ${cur_pos^} (change)"
)

active=""
for i in "${!THEMES[@]}"; do [ "${THEMES[$i]}" = "$cur_theme" ] && active="$i"; done

idx=$(printf '%s\n' "${LABELS[@]}" | rofi -dmenu -i -format i ${active:+-a "$active"} \
        -p "Waybar" -theme "$ROFI_THEME") || exit 0
[ -z "$idx" ] && exit 0

if [ "$idx" -lt "${#THEMES[@]}" ]; then
    apply --theme "${THEMES[$idx]}"
    exit $?
fi

# Position submenu
EDGES=(top bottom left right)
EDGE_LABELS=("󰁝  Top" "󰁅  Bottom" "󰁍  Left" "󰁔  Right")
pactive=""
for i in "${!EDGES[@]}"; do [ "${EDGES[$i]}" = "$cur_pos" ] && pactive="$i"; done

pidx=$(printf '%s\n' "${EDGE_LABELS[@]}" | rofi -dmenu -i -format i ${pactive:+-a "$pactive"} \
        -p "Position" -theme "$ROFI_THEME") || exit 0
[ -z "$pidx" ] && exit 0
apply --position "${EDGES[$pidx]}"
