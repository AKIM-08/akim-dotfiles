#!/usr/bin/env bash
# wifi-menu.sh - Rofi Wi-Fi menu (Waybar network module, left click)
# Lists networks by signal strength; connects to known networks directly and asks for a
# password for new secured ones. Uses NetworkManager (nmcli).

ROFI_THEME="$HOME/.config/rofi/settings.rasi"

# Toggle: clicking the module again closes the menu
if pgrep -f "rofi.*-p Wi-Fi" >/dev/null 2>&1; then
    pkill -f "rofi.*-p Wi-Fi" 2>/dev/null || true
    exit 0
fi

notify() {
    notify-send -h string:x-canonical-private-synchronous:wifi-menu -u low "Wi-Fi" "$1" 2>/dev/null || true
}

rofi_menu() {   # $1 = placeholder, extra args passed through; prints the selected index
    local placeholder="$1"; shift
    rofi -dmenu -i -p "Wi-Fi" -format i "$@" -theme "$ROFI_THEME" \
        -theme-str "entry { placeholder: \"$placeholder\"; }"
}

signal_icon() {
    local s="$1"
    if   [ "$s" -ge 80 ]; then echo "󰤨"
    elif [ "$s" -ge 60 ]; then echo "󰤥"
    elif [ "$s" -ge 40 ]; then echo "󰤢"
    elif [ "$s" -ge 20 ]; then echo "󰤟"
    else echo "󰤯"; fi
}

if ! command -v nmcli >/dev/null 2>&1; then
    notify "NetworkManager (nmcli) is not installed"
    exit 1
fi

radio=$(nmcli -t radio wifi 2>/dev/null)

labels=()
actions=()
active_rows=()

if [ "$radio" != "enabled" ]; then
    labels+=("󰖩  Turn Wi-Fi on")
    actions+=("radio-on")
else
    current=$(nmcli -t -e no -f ACTIVE,SSID dev wifi 2>/dev/null | awk -F: '$1=="yes" { sub(/^yes:/, ""); print; exit }')

    # One row per SSID (strongest access point), strongest first. Escaping off: SSID is the
    # last field, so `read` puts any colons in it into $ssid.
    declare -A seen=()
    while IFS=: read -r inuse signal security ssid; do
        [ -z "$ssid" ] && continue
        [ -n "${seen[$ssid]:-}" ] && continue
        seen[$ssid]=1
        lock=""; [ -n "$security" ] && [ "$security" != "--" ] && lock=" 󰌾"
        mark=""; [ "$ssid" = "$current" ] && { mark="  󰄬 connected"; active_rows+=("${#labels[@]}"); }
        labels+=("$(signal_icon "$signal")  ${ssid}${lock}${mark}")
        actions+=("net:$ssid:$security")
    done < <(nmcli -t -e no -f IN-USE,SIGNAL,SECURITY,SSID dev wifi list 2>/dev/null | sort -t: -k2,2nr)

    [ -n "$current" ] && { labels+=("󰖪  Disconnect from $current"); actions+=("disconnect"); }
    labels+=("󰑐  Rescan networks");        actions+=("rescan")
    labels+=("󰖪  Turn Wi-Fi off");          actions+=("radio-off")
fi
labels+=("󰒓  Advanced settings (nmtui)")
actions+=("advanced")

active_arg=()
[ ${#active_rows[@]} -gt 0 ] && active_arg=(-a "$(IFS=,; echo "${active_rows[*]}")")

idx=$(printf '%s\n' "${labels[@]}" | rofi_menu "Choose a network..." "${active_arg[@]}") || exit 0
[ -z "$idx" ] && exit 0
action="${actions[$idx]}"

case "$action" in
    radio-on)
        nmcli radio wifi on && notify "Wi-Fi turned on"
        sleep 2; exec "$0"
        ;;
    radio-off)
        nmcli radio wifi off && notify "Wi-Fi turned off"
        ;;
    rescan)
        notify "Scanning..."
        nmcli dev wifi rescan 2>/dev/null; sleep 3
        exec "$0"
        ;;
    disconnect)
        dev=$(nmcli -t -f DEVICE,TYPE,STATE dev | awk -F: '$2=="wifi" && $3=="connected" { print $1; exit }')
        [ -n "$dev" ] && nmcli dev disconnect "$dev" >/dev/null && notify "Disconnected"
        ;;
    advanced)
        kitty --class nmtui -e nmtui &
        ;;
    net:*)
        rest="${action#net:}"
        ssid="${rest%:*}"
        security="${rest##*:}"
        [ "$ssid" = "${current:-}" ] && exit 0

        if nmcli -t -f NAME con show 2>/dev/null | grep -Fxq "$ssid"; then
            notify "Connecting to $ssid..."
            if nmcli con up id "$ssid" >/dev/null 2>&1; then
                notify "Connected to $ssid"
            else
                notify "Could not connect to $ssid"
            fi
            exit 0
        fi

        if [ -n "$security" ] && [ "$security" != "--" ]; then
            pass=$(rofi -dmenu -password -p "Wi-Fi" -theme "$ROFI_THEME" \
                -theme-str "entry { placeholder: \"Password for $ssid\"; } listview { enabled: false; }" < /dev/null) || exit 0
            [ -z "$pass" ] && exit 0
            notify "Connecting to $ssid..."
            if nmcli dev wifi connect "$ssid" password "$pass" >/dev/null 2>&1; then
                notify "Connected to $ssid"
            else
                # Don't keep a saved profile with a wrong password
                nmcli con delete id "$ssid" >/dev/null 2>&1
                notify "Could not connect to $ssid (wrong password?)"
            fi
        else
            notify "Connecting to $ssid..."
            nmcli dev wifi connect "$ssid" >/dev/null 2>&1 \
                && notify "Connected to $ssid" || notify "Could not connect to $ssid"
        fi
        ;;
esac
