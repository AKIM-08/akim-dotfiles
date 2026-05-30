#!/bin/bash
# Hibernate when battery is at 1% and not on AC power

check_battery() {
    local bat_path capacity status
    for bat_path in /sys/class/power_supply/BAT*; do
        [ -d "$bat_path" ] || continue
        [ -f "$bat_path/capacity" ] || continue
        capacity=$(cat "$bat_path/capacity" 2>/dev/null)
        status=$(cat "$bat_path/status" 2>/dev/null)
        if [ -n "$capacity" ] && [ "$capacity" -le 1 ] && [ "$status" = "Discharging" ]; then
            return 0
        fi
    done
    return 1
}

while true; do
    if check_battery; then
        if [ -f "$HOME/.config/wlogout/hibernate.sh" ]; then
            bash "$HOME/.config/wlogout/hibernate.sh"
        else
            systemctl hibernate 2>/dev/null || notify-send "Power" "Hibernate failed (swap required?)" -u critical
        fi
        sleep 300
    fi
    sleep 30
done
