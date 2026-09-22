#!/usr/bin/env bash
# power-mode.sh - Manage system power profiles in Hyprland (GNOME Power Mode parity)
# Supports power-profiles-daemon, tlp, and cpupower fallbacks.

set -euo pipefail

# Get current power profile
get_current_profile() {
    if command -v powerprofilesctl &>/dev/null; then
        powerprofilesctl get 2>/dev/null || echo "balanced"
    elif [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
        gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null)
        case "$gov" in
            performance) echo "performance" ;;
            powersave) echo "power-saver" ;;
            *) echo "balanced" ;;
        esac
    else
        echo "balanced"
    fi
}

# Set power profile
set_profile() {
    local target="$1"
    local name=""
    local icon=""

    case "$target" in
        performance)
            name="Performance"
            icon="preferences-system-power"
            if command -v powerprofilesctl &>/dev/null; then
                powerprofilesctl set performance 2>/dev/null || true
            elif command -v cpupower &>/dev/null; then
                sudo cpupower frequency-set -g performance 2>/dev/null || true
            fi
            ;;
        balanced)
            name="Balanced"
            icon="preferences-system-power"
            if command -v powerprofilesctl &>/dev/null; then
                powerprofilesctl set balanced 2>/dev/null || true
            elif command -v cpupower &>/dev/null; then
                sudo cpupower frequency-set -g powersave 2>/dev/null || true
            fi
            ;;
        power-saver|powersaver|saver)
            target="power-saver"
            name="Power Saver"
            icon="battery-low"
            if command -v powerprofilesctl &>/dev/null; then
                powerprofilesctl set power-saver 2>/dev/null || true
            elif command -v cpupower &>/dev/null; then
                sudo cpupower frequency-set -g powersave 2>/dev/null || true
            fi
            ;;
        *)
            echo "Unknown power profile: $target" >&2
            exit 1
            ;;
    esac

    if command -v notify-send &>/dev/null; then
        notify-send -a "Power Mode" -i "$icon" "Power Mode" "Switched to <b>$name</b> mode" -u normal
    fi
}

# Toggle through profiles
toggle_profile() {
    local current
    current=$(get_current_profile)
    case "$current" in
        performance) set_profile "balanced" ;;
        balanced) set_profile "power-saver" ;;
        *) set_profile "performance" ;;
    esac
}

# Interactive Rofi Power Mode Menu
show_menu() {
    local current
    current=$(get_current_profile)

    local p_perf="󰓅  Performance"
    local p_bal="󰾆  Balanced"
    local p_save="󰌪  Power Saver"
    local p_set="󰒓  Power Settings"

    case "$current" in
        performance) p_perf="󰓅  Performance  ✓" ;;
        power-saver)  p_save="󰌪  Power Saver  ✓" ;;
        *)            p_bal="󰾆  Balanced  ✓" ;;
    esac

    local selected
    selected=$(printf "%s\n%s\n%s\n%s" "$p_perf" "$p_bal" "$p_save" "$p_set" | \
        rofi -dmenu -i -p "󰌪 Power Mode" -theme "$HOME/.config/rofi/powermode.rasi")

    case "$selected" in
        *"Performance"*) set_profile "performance" ;;
        *"Balanced"*)    set_profile "balanced" ;;
        *"Power Saver"*) set_profile "power-saver" ;;
        *"Power Settings"*)
            if command -v gnome-control-center &>/dev/null; then
                gnome-control-center power &
            elif command -v xfce4-power-manager-settings &>/dev/null; then
                xfce4-power-manager-settings &
            else
                kitty --class btop-system -e btop &
            fi
            ;;
    esac
}

# Action dispatch
ACTION="${1:-menu}"

case "$ACTION" in
    menu|"")
        show_menu
        ;;
    get)
        get_current_profile
        ;;
    toggle)
        toggle_profile
        ;;
    performance|balanced|power-saver|powersaver|saver)
        set_profile "$ACTION"
        ;;
    *)
        echo "Usage: $0 [menu|get|toggle|performance|balanced|power-saver]" >&2
        exit 1
        ;;
esac
