#!/bin/bash
# caffeine-toggle.sh - Toggle Caffeine Mode (prevent screen lock, DPMS off, and sleep)

STATE_FILE="$HOME/.cache/caffeine_active"
PID_FILE="$HOME/.cache/caffeine_inhibit.pid"

mkdir -p "$HOME/.cache"

if [ -f "$STATE_FILE" ]; then
    # Disable Caffeine Mode
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    pkill -f "systemd-inhibit --why=Caffeine" 2>/dev/null || true

    # Restart hypridle
    if ! pgrep -x hypridle >/dev/null; then
        hypridle & disown
    fi

    rm -f "$STATE_FILE"

    # Display clean top OSD banner only (in English, no bottom notification toast)
    hyprctl notify 1 3000 "rgb(f38ba8)" "☕ Caffeine Mode Disabled" 2>/dev/null || true
else
    # Enable Caffeine Mode
    rm -f "$STATE_FILE" "$PID_FILE"

    # Inhibit idle, sleep, and lid switch
    systemd-inhibit --why="Caffeine mode" --what=idle:sleep:handle-lid-switch sleep infinity &
    inhibit_pid=$!
    echo "$inhibit_pid" > "$PID_FILE"
    touch "$STATE_FILE"

    # Stop hypridle during Caffeine mode
    pkill -x hypridle 2>/dev/null || true

    # Display clean top OSD banner only (in English, no bottom notification toast)
    hyprctl notify 2 3000 "rgb(a6e3a1)" "☕ Caffeine Mode Enabled" 2>/dev/null || true
fi
