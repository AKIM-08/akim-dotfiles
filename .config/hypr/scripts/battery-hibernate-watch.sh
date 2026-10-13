#!/bin/bash
# battery-hibernate-watch.sh - Hibernate automatically when battery is almost empty (~5 minutes left)
# Automatically disables Caffeine Mode if active, to allow sleep/hibernation.

LOW_NOTIFIED=false

disable_caffeine() {
    if [ -f "$HOME/.cache/caffeine_active" ] || pgrep -f "systemd-inhibit.*[Cc]affeine" >/dev/null 2>&1; then
        if [ -x "$HOME/.config/hypr/scripts/caffeine-toggle.sh" ]; then
            bash "$HOME/.config/hypr/scripts/caffeine-toggle.sh" 2>/dev/null || true
        fi
        if [ -f "$HOME/.cache/caffeine_inhibit.pid" ]; then
            kill "$(cat "$HOME/.cache/caffeine_inhibit.pid" 2>/dev/null)" 2>/dev/null || true
            rm -f "$HOME/.cache/caffeine_inhibit.pid"
        fi
        pkill -f "systemd-inhibit.*[Cc]affeine" 2>/dev/null || true
        rm -f "$HOME/.cache/caffeine_active"
        notify-send -h string:x-canonical-private-synchronous:sys-notify -u normal \
            "Caffeine Mode" "Disabled automatically due to critical battery ⚠️" 2>/dev/null || true
    fi
}

check_battery() {
    # Returns 0 if battery is critical (~5 minutes or <= 4% remaining while discharging)
    # Returns 2 if battery is low (~10 minutes or <= 10%)
    # Returns 1 otherwise
    local bat_path status capacity energy_now power_now charge_now current_now
    local minutes_left=0
    local is_discharging=false
    local lowest_cap=100
    local min_minutes=9999

    for bat_path in /sys/class/power_supply/BAT*; do
        [ -d "$bat_path" ] || continue
        [ -f "$bat_path/status" ] || continue

        status=$(cat "$bat_path/status" 2>/dev/null)
        [ "$status" = "Discharging" ] || continue
        is_discharging=true

        capacity=$(cat "$bat_path/capacity" 2>/dev/null)
        if [ -n "$capacity" ] && [ "$capacity" -lt "$lowest_cap" ]; then
            lowest_cap="$capacity"
        fi

        # Calculate time remaining from energy or charge
        if [ -f "$bat_path/energy_now" ] && [ -f "$bat_path/power_now" ]; then
            energy_now=$(cat "$bat_path/energy_now" 2>/dev/null)
            power_now=$(cat "$bat_path/power_now" 2>/dev/null)
            if [ -n "$power_now" ] && [ "$power_now" -gt 0 ] 2>/dev/null && [ -n "$energy_now" ]; then
                minutes_left=$(( (energy_now * 60) / power_now ))
            fi
        elif [ -f "$bat_path/charge_now" ] && [ -f "$bat_path/current_now" ]; then
            charge_now=$(cat "$bat_path/charge_now" 2>/dev/null)
            current_now=$(cat "$bat_path/current_now" 2>/dev/null)
            if [ -n "$current_now" ] && [ "$current_now" -gt 0 ] 2>/dev/null && [ -n "$charge_now" ]; then
                minutes_left=$(( (charge_now * 60) / current_now ))
            fi
        fi

        # Fallback to upower if available and sysfs rates were missing
        if [ "$minutes_left" -eq 0 ] && command -v upower >/dev/null 2>&1; then
            local upower_dev time_str
            upower_dev=$(upower -e 2>/dev/null | grep -i 'battery' | head -1)
            if [ -n "$upower_dev" ]; then
                time_str=$(upower -i "$upower_dev" 2>/dev/null | grep -i 'time to empty' | awk '{print $4, $5}')
                if echo "$time_str" | grep -qi 'minute'; then
                    minutes_left=$(echo "$time_str" | awk '{print int($1)}')
                elif echo "$time_str" | grep -qi 'hour'; then
                    minutes_left=$(awk "BEGIN {print int($(echo "$time_str" | awk '{print $1}') * 60)}")
                fi
            fi
        fi

        if [ "$minutes_left" -gt 0 ] && [ "$minutes_left" -lt "$min_minutes" ]; then
            min_minutes="$minutes_left"
        fi
    done

    [ "$is_discharging" = true ] || return 1

    # Check for critical state: <= 5 minutes or <= 4%
    if [ "$min_minutes" -le 5 ] || [ "$lowest_cap" -le 4 ]; then
        return 0
    fi

    # Check for low battery warning: <= 10 minutes or <= 10%
    if [ "$min_minutes" -le 10 ] || [ "$lowest_cap" -le 10 ]; then
        return 2
    fi

    return 1
}

while true; do
    check_battery
    res=$?

    if [ "$res" -eq 0 ]; then
        # CRITICAL BATTERY: Disable Caffeine & Hibernate
        disable_caffeine

        notify-send -h string:x-canonical-private-synchronous:sys-notify -u critical \
            "Battery Critical" "Battery almost depleted (~5 min left). Hibernating to preserve session..." 2>/dev/null || true
        sleep 2

        # CRITICAL SECURITY: Explicitly launch hyprlock and ensure screen is locked before hibernation
        if ! pidof hyprlock >/dev/null 2>&1; then
            hyprlock &
            for _ in $(seq 1 30); do
                if pidof hyprlock >/dev/null 2>&1; then
                    break
                fi
                sleep 0.1
            done
            # Ensure hyprlock has grabbed the Wayland display and surface
            sleep 1.5
        fi

        loginctl lock-session 2>/dev/null || true
        sleep 1

        if [ -f "$HOME/.config/wlogout/hibernate.sh" ]; then
            bash "$HOME/.config/wlogout/hibernate.sh"
        else
            systemctl hibernate 2>/dev/null || {
                # Fallback if hibernation fails (e.g. no swap partition configured)
                notify-send -u critical "Power" "Hibernate failed (swap missing?). Suspending instead..." 2>/dev/null || true
                systemctl suspend-then-hibernate 2>/dev/null || systemctl suspend 2>/dev/null || true
            }
        fi
        sleep 300
        LOW_NOTIFIED=false
    elif [ "$res" -eq 2 ]; then
        if [ "$LOW_NOTIFIED" = false ]; then
            notify-send -h string:x-canonical-private-synchronous:sys-notify -u critical \
                "Battery Low" "Battery has ~10 minutes remaining. Please connect charger." 2>/dev/null || true
            LOW_NOTIFIED=true
        fi
    else
        LOW_NOTIFIED=false
    fi

    sleep 20
done
