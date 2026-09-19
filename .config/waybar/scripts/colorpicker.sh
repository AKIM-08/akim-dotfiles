#!/usr/bin/env bash
check() {
  command -v "$1" 1>/dev/null
}



loc="$HOME/.cache/colorpicker"
[ -d "$loc" ] || mkdir -p "$loc"
[ -f "$loc/colors" ] || touch "$loc/colors"

limit=10

[[ $# -eq 1 && $1 = "-l" ]] && {
  cat "$loc/colors"
  exit
}

[[ $# -eq 1 && $1 = "-j" ]] && {
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

  exit
}

check hyprpicker || {
  notify-send "hyprpicker is not installed"
  exit
}
killall -q hyprpicker
color=$(hyprpicker)

check wl-copy && {
  echo "$color" | sed -z 's/\n//g' | wl-copy
}

prevColors=$(head -n $((limit - 1)) "$loc/colors")
echo "$color" >"$loc/colors"
echo "$prevColors" >>"$loc/colors"
sed -i '/^$/d' "$loc/colors"
source ~/.cache/wal/colors.sh 2>/dev/null
notify-send "Color Picker" "This color has been selected: $color" \
    -i "${wallpaper:-$HOME/Pictures/wallpapers/current.jpg}"
pkill -RTMIN+1 waybar
