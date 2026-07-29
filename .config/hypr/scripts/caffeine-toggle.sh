#!/bin/bash
# caffeine-toggle.sh - Toggle Caffeine Mode (prevent screen lock, DPMS off, and sleep)

STATE_FILE="$HOME/.cache/caffeine_active"
PID_FILE="$HOME/.cache/caffeine_inhibit.pid"

mkdir -p "$HOME/.cache"

if [ -f "$STATE_FILE" ]; then
    # Mode Caféine déjà actif -> Désactivation
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    pkill -f "systemd-inhibit --why=Caffeine" 2>/dev/null || true

    # Relancer hypridle si non actif
    if ! pgrep -x hypridle >/dev/null; then
        hypridle & disown
    fi

    rm -f "$STATE_FILE"

    # Bannière pop-up à l'écran (OSD Hyprland en haut de l'écran + SwayNC toast)
    hyprctl notify 1 3500 "rgb(f38ba8)" "☕ Mode Caffeine : DESACTIF (Veille normale)" 2>/dev/null || true
    notify-send "☕ Mode Caféine : DÉSACTIVÉ" "La veille automatique et le verrouillage d'écran sont réactivés." -u critical
else
    # Activation du Mode Caféine
    rm -f "$STATE_FILE" "$PID_FILE"

    # Bloquer l'inactivité système et la veille via systemd-inhibit
    systemd-inhibit --why="Caffeine mode" --what=idle:sleep:handle-lid-switch sleep infinity &
    inhibit_pid=$!
    echo "$inhibit_pid" > "$PID_FILE"
    touch "$STATE_FILE"

    # Arrêter hypridle pendant le mode caféine pour empêcher hyprlock / DPMS off
    pkill -x hypridle 2>/dev/null || true

    # Bannière pop-up à l'écran (OSD Hyprland en haut de l'écran + SwayNC toast)
    hyprctl notify 2 3500 "rgb(a6e3a1)" "☕ Mode Caffeine : ACTIF (Anti-veille)" 2>/dev/null || true
    notify-send "☕ Mode Caféine : ACTIVÉ" "Votre ordinateur ne se mettra ni en veille ni en verrouillage." -u critical
fi
