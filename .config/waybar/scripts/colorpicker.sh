#!/usr/bin/env bash
# colorpicker.sh - Cross-distro Wayland color picker for Waybar

loc="$HOME/.cache/colorpicker"
[ -d "$loc" ] || mkdir -p "$loc"
[ -f "$loc/colors" ] || touch "$loc/colors"

limit=10

if [[ $# -eq 1 && "$1" == "-l" ]]; then
    cat "$loc/colors"
    exit 0
fi

if [[ $# -eq 1 && "$1" == "-j" ]]; then
    raw_text="$(head -n 1 "$loc/colors" 2>/dev/null)"
    text="${raw_text:-#ffffff}"

    if [ -s "$loc/colors" ]; then
        mapfile -t allcolors < <(tail -n +2 "$loc/colors")
        tooltip="<b>   COLORS</b>\n\n"
        tooltip+="-> <b>$text</b>  <span color='$text'></span>  \n"
        for i in "${allcolors[@]}"; do
            [ -n "$i" ] && tooltip+="   <b>$i</b>  <span color='$i'></span>  \n"
        done
    else
        tooltip="<b>Color Picker</b>\nClick to pick a color"
    fi

    cat <<EOF
{ "text":"<span color='$text'></span>", "tooltip":"$tooltip"}  
EOF
    exit 0
fi

# Pick color (hyprpicker or grim+slurp fallback)
color=""
if command -v hyprpicker &>/dev/null; then
    killall -q hyprpicker 2>/dev/null || true
    color=$(hyprpicker 2>/dev/null || true)
elif command -v grim &>/dev/null && command -v slurp &>/dev/null; then
    point=$(slurp -p -b 00000000 2>/dev/null || true)
    if [ -n "$point" ]; then
        color=$(grim -g "$point" -t ppm - 2>/dev/null | python3 -c '
import sys
data = sys.stdin.buffer.read()
newlines = 0
header_end = 0
for i in range(len(data)):
    if data[i] == 10:
        newlines += 1
        if newlines == 3:
            header_end = i + 1
            break
rgb = data[header_end:header_end+3]
if len(rgb) == 3:
    print(f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
' 2>/dev/null || true)
    fi
elif command -v wl-color-picker &>/dev/null; then
    color=$(wl-color-picker 2>/dev/null || true)
fi

if [ -z "$color" ]; then
    exit 0
fi

# Copy to clipboard
if command -v wl-copy &>/dev/null; then
    echo -n "$color" | wl-copy
fi

# Update recent colors
prevColors=$(head -n $((limit - 1)) "$loc/colors" 2>/dev/null || true)
echo "$color" > "$loc/colors"
[ -n "$prevColors" ] && echo "$prevColors" >> "$loc/colors"
sed -i '/^$/d' "$loc/colors"

# Notify
notify-send -h string:x-canonical-private-synchronous:sys-notify -u low "Color Picker" "Selected $color (copied to clipboard!)" 2>/dev/null || true

# Signal Waybar to refresh color icon
pkill -RTMIN+1 waybar 2>/dev/null || true
