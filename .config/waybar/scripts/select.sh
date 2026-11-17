#!/usr/bin/env bash
# select.sh - Waybar theme, position and size selector
#
#   select.sh                     open the menu (themes + Position + Size)
#   select.sh <theme>             apply a theme, keep position and size
#   select.sh --position <edge>   move the bar: top, bottom, left, right
#   select.sh --size <size>       bar thickness: compact, normal, large
#   select.sh --pick theme|position|size   open just that menu (used by Quick Settings)
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

# rofi_pick <prompt> <active index> <labels...>  -> prints the chosen index
rofi_pick() {
    local prompt="$1" active="$2"; shift 2
    printf '%s\n' "$@" | rofi -dmenu -i -format i ${active:+-a "$active"} -p "$prompt" \
        -theme "$ROFI_THEME" -theme-str "listview { lines: $#; }"
}

index_of() {   # index_of <value> <items...>
    local v="$1" i=0; shift
    for item in "$@"; do [ "$item" = "$v" ] && { echo "$i"; return; }; i=$((i + 1)); done
}

read -r cur_theme cur_pos cur_size < <(python3 "$LAYOUT" --get 2>/dev/null)

THEMES=(default line zen experimental capsule)
THEME_LABELS=(
    "󰕮  Default       —  Three floating islands"
    "󰤄  Line          —  Thin edge-to-edge strip"
    "󰾍  Zen           —  One island, drawer on hover"
    "󰘚  Experimental  —  Color bars, media, load"
    "󰍹  Capsule       —  Floating capsules"
)
EDGES=(top bottom left right)
EDGE_LABELS=("󰁝  Top" "󰁅  Bottom" "󰁍  Left" "󰁔  Right")
SIZES=(compact normal large)
SIZE_LABELS=("󰘕  Compact  —  Thinner bar, smaller text" "󰘖  Normal   —  Default" "󰁌  Large    —  Thicker bar, bigger text")

pick_theme() {
    local i; i=$(rofi_pick "Theme" "$(index_of "$cur_theme" "${THEMES[@]}")" "${THEME_LABELS[@]}") || return
    [ -n "$i" ] && apply --theme "${THEMES[$i]}"
}
pick_position() {
    local i; i=$(rofi_pick "Position" "$(index_of "$cur_pos" "${EDGES[@]}")" "${EDGE_LABELS[@]}") || return
    [ -n "$i" ] && apply --position "${EDGES[$i]}"
}
pick_size() {
    local i; i=$(rofi_pick "Size" "$(index_of "$cur_size" "${SIZES[@]}")" "${SIZE_LABELS[@]}") || return
    [ -n "$i" ] && apply --size "${SIZES[$i]}"
}

case "${1:-}" in
    --position) apply --position "${2:-top}"; exit $? ;;
    --size)     apply --size "${2:-normal}"; exit $? ;;
    --pick)
        case "${2:-}" in
            theme) pick_theme ;; position) pick_position ;; size) pick_size ;;
            *) echo "Usage: $0 --pick theme|position|size" >&2; exit 2 ;;
        esac
        exit 0 ;;
    "") ;;
    *) apply --theme "$1"; exit $? ;;
esac

# Main menu: themes, then Position and Size
labels=("${THEME_LABELS[@]}"
        "󰁌  Position      —  ${cur_pos^} (change)"
        "󰘖  Size          —  ${cur_size^} (change)")
idx=$(rofi_pick "Waybar" "$(index_of "$cur_theme" "${THEMES[@]}")" "${labels[@]}") || exit 0
[ -z "$idx" ] && exit 0

if [ "$idx" -lt "${#THEMES[@]}" ]; then
    apply --theme "${THEMES[$idx]}"
elif [ "$idx" -eq "${#THEMES[@]}" ]; then
    pick_position
else
    pick_size
fi
