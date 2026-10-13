#!/usr/bin/env bash
# quick-settings.sh — Quick Settings Control Center for Hyprland (SUPER + H)
# Change mouse speed, default applications, power profiles, and more interactively.

ROFI_THEME="$HOME/.config/rofi/settings.rasi"
USER_SETTINGS="$HOME/.config/hypr/user-settings.hl"

# Toggle support: If settings menu is already open, close it
if pgrep -f "rofi.*settings\.rasi" >/dev/null 2>&1; then
    pkill -f "rofi.*settings\.rasi" 2>/dev/null || true
    exit 0
fi

# Ensure user-settings file exists
touch "$USER_SETTINGS"

# Read current mouse sensitivity
get_sensitivity() {
    local val=""
    if [ -f "$USER_SETTINGS" ]; then
        val=$(grep -E '^[[:space:]]*sensitivity[[:space:]]*=' "$USER_SETTINGS" 2>/dev/null | tail -1 | awk -F'=' '{print $2}' | tr -d ' ')
    fi
    if [ -z "$val" ] && command -v hyprctl &>/dev/null; then
        val=$(hyprctl getoption input:sensitivity -j 2>/dev/null | grep -oP '"float":\s*\K[-0-9.]+' || true)
    fi
    echo "${val:-0.2}"
}

# Apply and persist mouse sensitivity
set_sensitivity() {
    local new_val="$1"
    [ -z "$new_val" ] && return

    # Validate numeric float between -1.0 and 1.0
    if ! [[ "$new_val" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
        notify-send -u critical "Settings" "Invalid sensitivity value: $new_val" 2>/dev/null || true
        return
    fi

    # 1. Apply immediately to running Hyprland session
    if command -v hyprctl &>/dev/null; then
        hyprctl keyword input:sensitivity "$new_val" 2>/dev/null || true
    fi

    # 2. Persist in ~/.config/hypr/user-settings.hl
    if grep -q "sensitivity" "$USER_SETTINGS" 2>/dev/null; then
        sed -i -E "s/^[[:space:]]*sensitivity[[:space:]]*=.*/    sensitivity = $new_val/" "$USER_SETTINGS"
    else
        cat << EOF >> "$USER_SETTINGS"

input {
    sensitivity = $new_val
}
EOF
    fi

    notify-send -h string:x-canonical-private-synchronous:sys-notify -u low \
        "Settings" "Mouse sensitivity set to: $new_val 🖱️" 2>/dev/null || true
}

# Mouse speed submenu
menu_mouse_speed() {
    local cur
    cur=$(get_sensitivity)
    local options="󰍽  +0.8  —  Very Fast\n󰍽  +0.5  —  Fast\n󰍽  +0.2  —  Default\n󰍽   0.0  —  Neutral\n󰍽  -0.3  —  Slow\n󰍽  -0.6  —  Very Slow\n󰍽  Custom —  Enter custom value (-1.0 to 1.0)"

    local choice
    choice=$(echo -e "$options" | rofi -dmenu -i -p "Sensitivity (Current: $cur)" -theme "$ROFI_THEME") || true
    [ -z "$choice" ] && return

    case "$choice" in
        *"+0.8"*) set_sensitivity 0.8 ;;
        *"+0.5"*) set_sensitivity 0.5 ;;
        *"+0.2"*) set_sensitivity 0.2 ;;
        *"0.0"*)  set_sensitivity 0.0 ;;
        *"-0.3"*) set_sensitivity -0.3 ;;
        *"-0.6"*) set_sensitivity -0.6 ;;
        *Custom*)
            local custom_val
            custom_val=$(rofi -dmenu -p "Enter sensitivity (-1.0 to 1.0)" -theme "$ROFI_THEME") || true
            [ -n "$custom_val" ] && set_sensitivity "$custom_val"
            ;;
    esac
}

# Default Web Browser Submenu
menu_default_browser() {
    local cur_desktop=""
    if command -v xdg-settings &>/dev/null; then
        cur_desktop=$(xdg-settings get default-web-browser 2>/dev/null || true)
    fi

    local available=()
    # Search for installed web browsers
    for b in firefox.desktop brave-browser.desktop google-chrome.desktop chromium.desktop \
             zen-browser.desktop zen.desktop opera.desktop vivaldi-stable.desktop epiphany.desktop; do
        if [ -f "/usr/share/applications/$b" ] || [ -f "$HOME/.local/share/applications/$b" ]; then
            local name
            name=$(grep -m1 '^Name=' "/usr/share/applications/$b" "$HOME/.local/share/applications/$b" 2>/dev/null | head -1 | cut -d'=' -f2)
            available+=("$name ($b)")
        fi
    done

    if [ ${#available[@]} -eq 0 ]; then
        notify-send "Settings" "No browsers found in application shortcuts."
        return
    fi

    local choice
    choice=$(printf "%s\n" "${available[@]}" | rofi -dmenu -i -p "Default Browser" -theme "$ROFI_THEME") || true
    [ -z "$choice" ] && return

    local selected_desktop
    selected_desktop=$(echo "$choice" | grep -oP '\(\K[^\)]+' || true)
    if [ -n "$selected_desktop" ]; then
        xdg-settings set default-web-browser "$selected_desktop" 2>/dev/null || true
        xdg-mime default "$selected_desktop" x-scheme-handler/http 2>/dev/null || true
        xdg-mime default "$selected_desktop" x-scheme-handler/https 2>/dev/null || true
        xdg-mime default "$selected_desktop" text/html 2>/dev/null || true
        notify-send -h string:x-canonical-private-synchronous:sys-notify -u low \
            "Settings" "Default browser changed to: $(echo "$choice" | cut -d'(' -f1 | xargs) 🌐" 2>/dev/null || true
    fi
}

# Default Terminal Submenu
menu_default_terminal() {
    local terminals=("Kitty (kitty)" "Alacritty (alacritty)" "Foot (foot)" "GNOME Terminal (gnome-terminal)" "Konsole (konsole)")
    local installed=()

    for t in "${terminals[@]}"; do
        local bin
        bin=$(echo "$t" | grep -oP '\(\K[^\)]+')
        if command -v "$bin" &>/dev/null; then
            installed+=("$t")
        fi
    done

    [ ${#installed[@]} -eq 0 ] && return

    local choice
    choice=$(printf "%s\n" "${installed[@]}" | rofi -dmenu -i -p "Default Terminal" -theme "$ROFI_THEME") || true
    [ -z "$choice" ] && return

    local bin
    bin=$(echo "$choice" | grep -oP '\(\K[^\)]+')

    # Update in user-settings.hl
    if grep -q "\$terminal" "$USER_SETTINGS" 2>/dev/null; then
        sed -i -E "s/^[[:space:]]*\\\$terminal[[:space:]]*=.*/\$terminal = $bin/" "$USER_SETTINGS"
    else
        echo "\$terminal = $bin" >> "$USER_SETTINGS"
    fi

    # Update alternatives if root or possible
    if command -v update-alternatives &>/dev/null && command -v sudo &>/dev/null; then
        sudo update-alternatives --set x-terminal-emulator "$(command -v "$bin")" 2>/dev/null || true
    fi

    notify-send -h string:x-canonical-private-synchronous:sys-notify -u low \
        "Settings" "Default terminal set to: $bin 💻" 2>/dev/null || true
}

# Default File Manager Submenu
menu_default_file_manager() {
    local managers=("Nautilus (nautilus)" "Dolphin (dolphin)" "Thunar (thunar)" "Nemo (nemo)" "PCManFM (pcmanfm)")
    local installed=()

    for m in "${managers[@]}"; do
        local bin
        bin=$(echo "$m" | grep -oP '\(\K[^\)]+')
        if command -v "$bin" &>/dev/null; then
            installed+=("$m")
        fi
    done

    [ ${#installed[@]} -eq 0 ] && return

    local choice
    choice=$(printf "%s\n" "${installed[@]}" | rofi -dmenu -i -p "Default File Manager" -theme "$ROFI_THEME") || true
    [ -z "$choice" ] && return

    local bin
    bin=$(echo "$choice" | grep -oP '\(\K[^\)]+')

    if grep -q "\$fileManager" "$USER_SETTINGS" 2>/dev/null; then
        sed -i -E "s/^[[:space:]]*\\\$fileManager[[:space:]]*=.*/\$fileManager = $bin/" "$USER_SETTINGS"
    else
        echo "\$fileManager = $bin" >> "$USER_SETTINGS"
    fi

    xdg-mime default "${bin}.desktop" inode/directory 2>/dev/null || true
    notify-send -h string:x-canonical-private-synchronous:sys-notify -u low \
        "Settings" "Default file manager set to: $bin 📁" 2>/dev/null || true
}

# Power Profile Submenu
menu_power_profile() {
    if command -v powerprofilesctl &>/dev/null; then
        local cur
        cur=$(powerprofilesctl get 2>/dev/null || echo "balanced")
        local options="⚡  Performance   —  Maximum performance\n⚖️  Balanced      —  Standard usage\n🍃  Power Saver   —  Extend battery life"

        local choice
        choice=$(echo -e "$options" | rofi -dmenu -i -p "Power Profile (Current: $cur)" -theme "$ROFI_THEME") || true
        [ -z "$choice" ] && return

        case "$choice" in
            *Performance*) powerprofilesctl set performance 2>/dev/null ;;
            *Balanced*)    powerprofilesctl set balanced 2>/dev/null ;;
            *Power*)       powerprofilesctl set power-saver 2>/dev/null ;;
        esac
        notify-send -h string:x-canonical-private-synchronous:sys-notify -u low \
            "Settings" "Power profile set to: $(powerprofilesctl get) 🔋" 2>/dev/null || true
    else
        notify-send "Settings" "powerprofilesctl not available."
    fi
}

# Main Settings Menu
cur_sens=$(get_sensitivity)
caffeine_status="OFF"
[ -f "$HOME/.cache/caffeine_active" ] && caffeine_status="ON"

MAIN_OPTIONS="󰍽  Mouse Speed / Sensitivity      —  Current: [${cur_sens}]\n󰖟  Default Web Browser           —  Configure default browser\n󰞷  Default Terminal Emulator     —  Configure default terminal\n󰉋  Default File Manager          —  Configure default file manager\n󰒓  Power Profile                 —  Performance / Balanced / Saver\n󰅶  Caffeine Mode (Anti-Sleep)     —  Status: [${caffeine_status}]\n󰌾  Lock Screen Now               —  Instant Lock (Super + L)\n󱄄  Waybar Theme Selector          —  Change status bar style\n󰸉  Wallpaper Selector             —  Pick Wallpaper (Super + W)\n󰕾  Sound / Volume Control        —  Open Audio Mixer\n󰂯  Bluetooth Manager             —  Open Bluetooth GUI\n󰤨  Network / Wi-Fi Connections   —  Open Network Settings\n󰌌  Shortcuts Cheatsheet           —  View All Keybinds (Super + G)\n󰋽  System Information            —  View Quick System Specs"

choice=$(echo -e "$MAIN_OPTIONS" | rofi -dmenu -i -p "󰒓 Settings" -theme "$ROFI_THEME") || true
[ -z "$choice" ] && exit 0

case "$choice" in
    *Mouse*)
        menu_mouse_speed
        ;;
    *Browser*)
        menu_default_browser
        ;;
    *Terminal*)
        menu_default_terminal
        ;;
    *File\ Manager*)
        menu_default_file_manager
        ;;
    *Power\ Profile*)
        menu_power_profile
        ;;
    *Caffeine*)
        bash "$HOME/.config/hypr/scripts/caffeine-toggle.sh"
        ;;
    *Lock*)
        pidof hyprlock >/dev/null 2>&1 || hyprlock
        ;;
    *Waybar*)
        bash "$HOME/.config/waybar/scripts/select.sh"
        ;;
    *Wallpaper*)
        bash "$HOME/.config/hypr/scripts/rofi-wallpaper.sh"
        ;;
    *Sound*)
        if command -v pavucontrol &>/dev/null; then
            pavucontrol &
        else
            notify-send "Audio" "pavucontrol is not installed."
        fi
        ;;
    *Bluetooth*)
        if command -v blueman-manager &>/dev/null; then
            blueman-manager &
        else
            notify-send "Bluetooth" "blueman-manager is not installed."
        fi
        ;;
    *Network*)
        if command -v nm-connection-editor &>/dev/null; then
            nm-connection-editor &
        else
            notify-send "Network" "nm-connection-editor is not installed."
        fi
        ;;
    *Shortcuts*)
        bash "$HOME/.config/hypr/scripts/keybinds.sh"
        ;;
    *System\ Information*)
        if command -v fastfetch &>/dev/null; then
            kitty --hold fastfetch &
        else
            notify-send "System" "$(uname -a)"
        fi
        ;;
esac
