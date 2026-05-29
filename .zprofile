# Login shell only — auto-start Hyprland on tty1 (requires systemd autologin)
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(tty)" = "/dev/tty1" ]; then
    if command -v Hyprland &>/dev/null; then
        exec Hyprland
    else
        echo "Hyprland not found — install with: sudo pacman -S hyprland" >&2
    fi
fi
