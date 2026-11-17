#!/usr/bin/env bash
# quick-settings.sh — Quick Settings Control Center for Hyprland (SUPER + H)
# Appearance, connectivity, toggles, input and default applications in one Rofi menu.

ROFI_THEME="$HOME/.config/rofi/settings.rasi"
HYPR_DIR="$HOME/.config/hypr"
SCRIPTS="$HYPR_DIR/scripts"
USER_SETTINGS="$HYPR_DIR/user-settings.hl"   # sourced at the end of hyprland.hl (input, animations)
USER_APPS="$HYPR_DIR/user-apps.hl"           # sourced before the keybinds ($terminal, $fileManager)
WAYBAR_SELECT="$HOME/.config/waybar/scripts/select.sh"

# Toggle support: if the settings menu is already open, close it
if pgrep -f "rofi.*settings\.rasi" >/dev/null 2>&1; then
    pkill -f "rofi.*settings\.rasi" 2>/dev/null || true
    exit 0
fi

touch "$USER_SETTINGS" "$USER_APPS"

notify() {
    notify-send -h string:x-canonical-private-synchronous:sys-notify -u low "Settings" "$1" 2>/dev/null || true
}

# rofi_pick <prompt> <active index or ""> <labels...>  -> prints the chosen index
rofi_pick() {
    local prompt="$1" active="$2"; shift 2
    local lines=$(( $# < 10 ? $# : 10 ))
    printf '%s\n' "$@" | rofi -dmenu -i -format i ${active:+-a "$active"} -p "$prompt" \
        -theme "$ROFI_THEME" -theme-str "listview { lines: $lines; }"
}

# Replace (or append) a block between markers in user-settings.hl
set_block() {   # set_block <name> <content>
    local name="$1" content="$2" begin="# >>> quick-settings: $1" end="# <<< quick-settings: $1"
    local tmp; tmp=$(mktemp)
    awk -v b="$begin" -v e="$end" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$USER_SETTINGS" > "$tmp"
    printf '%s\n%s\n%s\n' "$begin" "$content" "$end" >> "$tmp"
    cat "$tmp" > "$USER_SETTINGS"; rm -f "$tmp"
}

# Set a variable in user-apps.hl (and drop old, ineffective copies from user-settings.hl)
set_app_var() {   # set_app_var <name> <command>
    local name="$1" value="$2"
    sed -i "/^[[:space:]]*\\\$$name[[:space:]]*=/d" "$USER_APPS" "$USER_SETTINGS" 2>/dev/null
    echo "\$$name = $value" >> "$USER_APPS"
}

# ---------------------------------------------------------------- Mouse speed
get_sensitivity() {
    local val
    val=$(grep -E '^[[:space:]]*sensitivity[[:space:]]*=' "$USER_SETTINGS" 2>/dev/null | tail -1 | awk -F'=' '{print $2}' | tr -d ' ')
    if [ -z "$val" ] && command -v hyprctl &>/dev/null; then
        val=$(hyprctl getoption input:sensitivity -j 2>/dev/null | grep -oP '"float":\s*\K[-0-9.]+' || true)
    fi
    echo "${val:-0.2}"
}

set_sensitivity() {
    local v="$1"
    if ! [[ "$v" =~ ^-?(0(\.[0-9]+)?|1(\.0+)?)$ ]]; then
        notify-send -u critical "Settings" "Invalid sensitivity: $v (use a number from -1.0 to 1.0)" 2>/dev/null
        return
    fi
    hyprctl keyword input:sensitivity "$v" >/dev/null 2>&1
    # Drop the old unmarked block written by earlier versions, then write ours
    if grep -q "^input {$" "$USER_SETTINGS" && ! grep -q "quick-settings: mouse" "$USER_SETTINGS"; then
        sed -i '/^[[:space:]]*sensitivity[[:space:]]*=/d' "$USER_SETTINGS"
    fi
    set_block mouse "input {
    sensitivity = $v
}"
    notify "Mouse sensitivity set to $v"
}

menu_mouse_speed() {
    local cur values labels i
    cur=$(get_sensitivity)
    values=(0.8 0.5 0.2 0.0 -0.3 -0.6 custom)
    labels=("󰍽  +0.8  —  Very fast" "󰍽  +0.5  —  Fast" "󰍽  +0.2  —  Default" "󰍽   0.0  —  Neutral"
            "󰍽  -0.3  —  Slow" "󰍽  -0.6  —  Very slow" "󰏫  Custom value (-1.0 to 1.0)")
    i=$(rofi_pick "Mouse speed ($cur)" "" "${labels[@]}") || return
    [ -z "$i" ] && return
    if [ "${values[$i]}" = custom ]; then
        local v
        v=$(rofi -dmenu -p "Sensitivity" -theme "$ROFI_THEME" \
              -theme-str 'entry { placeholder: "-1.0 to 1.0"; } listview { enabled: false; }' < /dev/null) || return
        [ -n "$v" ] && set_sensitivity "$v"
    else
        set_sensitivity "${values[$i]}"
    fi
}

# ---------------------------------------------------------------- Default apps
menu_default_browser() {
    local dirs=(/usr/share/applications "$HOME/.local/share/applications"
                /var/lib/flatpak/exports/share/applications "$HOME/.local/share/flatpak/exports/share/applications")
    local ids=() labels=() cur active="" f id name
    cur=$(xdg-settings get default-web-browser 2>/dev/null)
    declare -A seen=()

    # Every installed app that declares itself a web browser (incl. Firefox ESR and Flatpaks)
    for d in "${dirs[@]}"; do
        for f in "$d"/*.desktop; do
            [ -f "$f" ] || continue
            id=$(basename "$f")
            [ -n "${seen[$id]:-}" ] && continue
            grep -q '^Categories=.*WebBrowser' "$f" || continue
            grep -qi '^NoDisplay=true' "$f" && continue
            seen[$id]=1
            name=$(grep -m1 '^Name=' "$f" | cut -d= -f2-)
            [ "$id" = "$cur" ] && active="${#ids[@]}"
            ids+=("$id"); labels+=("󰖟  $name")
        done
    done

    if [ ${#ids[@]} -eq 0 ]; then notify "No web browsers found"; return; fi
    local i; i=$(rofi_pick "Default browser" "$active" "${labels[@]}") || return
    [ -z "$i" ] && return
    id="${ids[$i]}"
    xdg-settings set default-web-browser "$id" 2>/dev/null
    xdg-mime default "$id" x-scheme-handler/http x-scheme-handler/https text/html 2>/dev/null
    notify "Default browser: ${labels[$i]#*  }"
}

menu_default_terminal() {
    local bins=(kitty alacritty foot wezterm gnome-terminal konsole) names=(Kitty Alacritty Foot WezTerm "GNOME Terminal" Konsole)
    local found=() labels=() active="" cur i
    cur=$(grep -oP '^\$terminal\s*=\s*\K\S+' "$USER_APPS" 2>/dev/null | tail -1); cur="${cur:-kitty}"
    for i in "${!bins[@]}"; do
        command -v "${bins[$i]}" &>/dev/null || continue
        [ "${bins[$i]}" = "$cur" ] && active="${#found[@]}"
        found+=("${bins[$i]}"); labels+=("󰞷  ${names[$i]}")
    done
    [ ${#found[@]} -eq 0 ] && { notify "No supported terminal found"; return; }
    i=$(rofi_pick "Default terminal" "$active" "${labels[@]}") || return
    [ -z "$i" ] && return
    set_app_var terminal "${found[$i]}"
    notify "Default terminal: ${labels[$i]#*  } (Super + Return)"
}

menu_default_file_manager() {
    local bins=(nautilus thunar nemo dolphin pcmanfm) names=(Nautilus Thunar Nemo Dolphin PCManFM)
    local cmds=("nautilus --new-window" thunar nemo dolphin pcmanfm)
    local found=() labels=() active="" cur i
    cur=$(grep -oP '^\$fileManager\s*=\s*\K\S+' "$USER_APPS" 2>/dev/null | tail -1); cur="${cur:-nautilus}"
    for i in "${!bins[@]}"; do
        command -v "${bins[$i]}" &>/dev/null || continue
        [ "${bins[$i]}" = "$cur" ] && active="${#found[@]}"
        found+=("$i"); labels+=("󰉋  ${names[$i]}")
    done
    [ ${#found[@]} -eq 0 ] && { notify "No supported file manager found"; return; }
    local k; k=$(rofi_pick "Default file manager" "$active" "${labels[@]}") || return
    [ -z "$k" ] && return
    i="${found[$k]}"
    set_app_var fileManager "${cmds[$i]}"
    local desktop
    desktop=$(grep -l "^Exec=${bins[$i]}" /usr/share/applications/*.desktop 2>/dev/null | head -1)
    [ -n "$desktop" ] && xdg-mime default "$(basename "$desktop")" inode/directory 2>/dev/null
    notify "Default file manager: ${names[$i]} (Super + F)"
}

# ---------------------------------------------------------------- Waybar
menu_waybar() {
    local theme pos size i
    read -r theme pos size < <(python3 "$HOME/.config/waybar/scripts/layout.py" --get 2>/dev/null)
    i=$(rofi_pick "Waybar" "" "󰕮  Theme     —  ${theme^}" "󰁌  Position  —  ${pos^}" "󰘖  Size      —  ${size^}") || return
    case "$i" in
        0) bash "$WAYBAR_SELECT" --pick theme ;;
        1) bash "$WAYBAR_SELECT" --pick position ;;
        2) bash "$WAYBAR_SELECT" --pick size ;;
    esac
}

# ---------------------------------------------------------------- Toggles
dnd_state() { [ "$(swaync-client -D 2>/dev/null)" = "true" ] && echo ON || echo OFF; }

animations_state() {
    hyprctl getoption animations:enabled -j 2>/dev/null | grep -q '"int": *0' && echo OFF || echo ON
}
toggle_animations() {
    if [ "$(animations_state)" = ON ]; then
        hyprctl keyword animations:enabled 0 >/dev/null
        set_block animations "animations {
    enabled = false
}"
        notify "Animations off (snappier, saves battery)"
    else
        hyprctl keyword animations:enabled 1 >/dev/null
        set_block animations "animations {
    enabled = true
}"
        notify "Animations on"
    fi
}

menu_power_profile() {
    if ! command -v powerprofilesctl &>/dev/null; then notify "powerprofilesctl is not installed"; return; fi
    local cur profiles labels active="" i
    cur=$(powerprofilesctl get 2>/dev/null)
    profiles=(performance balanced power-saver)
    labels=("󰓅  Performance  —  Maximum speed" "󰾅  Balanced     —  Everyday use" "󰾆  Power saver  —  Longer battery life")
    for i in "${!profiles[@]}"; do [ "${profiles[$i]}" = "$cur" ] && active="$i"; done
    i=$(rofi_pick "Power profile" "$active" "${labels[@]}") || return
    [ -z "$i" ] && return
    powerprofilesctl set "${profiles[$i]}" 2>/dev/null && notify "Power profile: ${profiles[$i]}"
}

# ---------------------------------------------------------------- Main menu
caffeine="OFF"; [ -f "$HOME/.cache/caffeine_active" ] && caffeine="ON"
power=$(powerprofilesctl get 2>/dev/null || echo "n/a")
read -r wb_theme wb_pos wb_size < <(python3 "$HOME/.config/waybar/scripts/layout.py" --get 2>/dev/null)

ENTRIES=(
    "wallpaper|󰸉  Wallpaper                  —  Pick a wallpaper (Super + W)"
    "waybar|󱄄  Waybar                     —  ${wb_theme^}, ${wb_pos}, ${wb_size}"
    "wifi|󰤨  Wi-Fi                      —  Networks"
    "bluetooth|󰂯  Bluetooth                  —  Devices"
    "sound|󰕾  Sound                      —  Audio mixer"
    "dnd|󰂛  Do Not Disturb             —  $(dnd_state)"
    "caffeine|󰅶  Caffeine (stay awake)      —  ${caffeine}"
    "animations|󰘕  Animations                 —  $(animations_state)"
    "power|󰒓  Power profile              —  ${power}"
    "mouse|󰍽  Mouse speed                —  $(get_sensitivity)"
    "browser|󰖟  Default web browser"
    "terminal|󰞷  Default terminal"
    "files|󰉋  Default file manager"
    "keys|󰌌  Keyboard shortcuts         —  Super + G"
    "info|󰋽  System information"
    "lock|󰌾  Lock screen                —  Super + L"
)
keys=(); labels=()
for e in "${ENTRIES[@]}"; do keys+=("${e%%|*}"); labels+=("${e#*|}"); done

i=$(printf '%s\n' "${labels[@]}" | rofi -dmenu -i -format i -p "󰒓 Settings" -theme "$ROFI_THEME") || exit 0
[ -z "$i" ] && exit 0

case "${keys[$i]}" in
    wallpaper)  bash "$SCRIPTS/rofi-wallpaper.sh" ;;
    waybar)     menu_waybar ;;
    wifi)       bash "$SCRIPTS/wifi-menu.sh" ;;
    bluetooth)  bash "$SCRIPTS/bluetooth-menu.sh" ;;
    sound)      command -v pavucontrol &>/dev/null && { pavucontrol >/dev/null 2>&1 & } || notify "pavucontrol is not installed" ;;
    dnd)        swaync-client -d -sw >/dev/null 2>&1; notify "Do Not Disturb: $(dnd_state)" ;;
    caffeine)   bash "$SCRIPTS/caffeine-toggle.sh" ;;
    animations) toggle_animations ;;
    power)      menu_power_profile ;;
    mouse)      menu_mouse_speed ;;
    browser)    menu_default_browser ;;
    terminal)   menu_default_terminal ;;
    files)      menu_default_file_manager ;;
    keys)       bash "$SCRIPTS/keybinds.sh" ;;
    info)       if command -v fastfetch &>/dev/null; then kitty --hold fastfetch >/dev/null 2>&1 & else notify "$(uname -sr)"; fi ;;
    lock)       pidof hyprlock >/dev/null 2>&1 || hyprlock ;;
esac
