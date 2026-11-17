#!/usr/bin/env bash
# bluetooth-menu.sh - Rofi Bluetooth menu (Waybar bluetooth module, left click)
# Shows known and nearby devices with their state and battery; selecting a device
# connects, disconnects, or pairs it. Uses BlueZ (bluetoothctl).

ROFI_THEME="$HOME/.config/rofi/settings.rasi"
SCAN_SECONDS=8

if pgrep -f "rofi.*-p Bluetooth" >/dev/null 2>&1; then
    pkill -f "rofi.*-p Bluetooth" 2>/dev/null || true
    exit 0
fi

notify() {
    notify-send -h string:x-canonical-private-synchronous:bt-menu -u low "Bluetooth" "$1" 2>/dev/null || true
}

if ! command -v bluetoothctl >/dev/null 2>&1; then
    notify "BlueZ (bluetoothctl) is not installed"
    exit 1
fi

device_icon() {
    case "$1" in
        audio-headset|audio-headphones) echo "󰋋" ;;
        audio-card)                     echo "󰓃" ;;
        input-keyboard)                 echo "󰌌" ;;
        input-mouse)                    echo "󰍽" ;;
        input-gaming)                   echo "󰊴" ;;
        phone)                          echo "󰏲" ;;
        computer)                       echo "󰟀" ;;
        *)                              echo "󰂯" ;;
    esac
}

powered=$(bluetoothctl show 2>/dev/null | awk '/Powered:/ { print $2; exit }')

labels=()
actions=()
active_rows=()

if [ "$powered" != "yes" ]; then
    labels+=("󰂯  Turn Bluetooth on")
    actions+=("power-on")
else
    # Connected devices first, then paired, then nearby ones
    rows_connected=(); acts_connected=()
    rows_paired=();    acts_paired=()
    rows_other=();     acts_other=()

    while read -r _ mac name; do
        [ -z "$mac" ] && continue
        info=$(bluetoothctl info "$mac" 2>/dev/null)
        icon=$(device_icon "$(awk '/Icon:/ { print $2; exit }' <<<"$info")")
        battery=$(sed -n 's/.*Battery Percentage:.*(\([0-9]*\)).*/\1/p' <<<"$info" | head -1)
        bat=""; [ -n "$battery" ] && bat="  󰁹 ${battery}%"

        if grep -q "Connected: yes" <<<"$info"; then
            rows_connected+=("$icon  $name  󰄬 connected$bat"); acts_connected+=("disconnect:$mac:$name")
        elif grep -q "Paired: yes" <<<"$info"; then
            rows_paired+=("$icon  $name"); acts_paired+=("connect:$mac:$name")
        else
            rows_other+=("$icon  $name  (new)"); acts_other+=("pair:$mac:$name")
        fi
    done < <(bluetoothctl devices 2>/dev/null)

    for i in "${!rows_connected[@]}"; do
        active_rows+=("${#labels[@]}")
        labels+=("${rows_connected[$i]}"); actions+=("${acts_connected[$i]}")
    done
    labels+=("${rows_paired[@]}");  actions+=("${acts_paired[@]}")
    labels+=("${rows_other[@]}");   actions+=("${acts_other[@]}")

    labels+=("󰑐  Scan for devices (${SCAN_SECONDS}s)"); actions+=("scan")
    labels+=("󰂲  Turn Bluetooth off");                  actions+=("power-off")
fi
labels+=("󰒓  Advanced settings (Blueman)")
actions+=("advanced")

active_arg=()
[ ${#active_rows[@]} -gt 0 ] && active_arg=(-a "$(IFS=,; echo "${active_rows[*]}")")

idx=$(printf '%s\n' "${labels[@]}" | rofi -dmenu -i -p "Bluetooth" -format i "${active_arg[@]}" \
    -theme "$ROFI_THEME" -theme-str 'entry { placeholder: "Choose a device..."; }') || exit 0
[ -z "$idx" ] && exit 0
action="${actions[$idx]}"
kind="${action%%:*}"
rest="${action#*:}"
# MAC addresses contain colons: take the 17-char MAC and the name after it
mac="${rest:0:17}"
name="${rest:18}"

case "$kind" in
    power-on)
        rfkill unblock bluetooth 2>/dev/null
        bluetoothctl power on >/dev/null && notify "Bluetooth turned on"
        sleep 1; exec "$0"
        ;;
    power-off)
        bluetoothctl power off >/dev/null && notify "Bluetooth turned off"
        ;;
    scan)
        notify "Scanning for ${SCAN_SECONDS}s..."
        bluetoothctl --timeout "$SCAN_SECONDS" scan on >/dev/null 2>&1
        exec "$0"
        ;;
    connect)
        notify "Connecting to $name..."
        bluetoothctl connect "$mac" >/dev/null 2>&1 \
            && notify "Connected to $name" || notify "Could not connect to $name"
        ;;
    disconnect)
        bluetoothctl disconnect "$mac" >/dev/null 2>&1 && notify "Disconnected $name"
        ;;
    pair)
        notify "Pairing with $name..."
        if bluetoothctl pair "$mac" >/dev/null 2>&1; then
            bluetoothctl trust "$mac" >/dev/null 2>&1
            bluetoothctl connect "$mac" >/dev/null 2>&1 \
                && notify "Paired and connected to $name" || notify "Paired with $name"
        else
            notify "Could not pair with $name. Put it in pairing mode and try again."
        fi
        ;;
    advanced)
        blueman-manager &
        ;;
esac
