#!/usr/bin/env bash
# open-browser.sh - Launch preferred/default browser for Hyprland (SUPER + B)

# 1. Respect $BROWSER environment variable if set
if [ -n "${BROWSER:-}" ] && command -v "$BROWSER" >/dev/null; then
    exec "$BROWSER"
fi

# 2. Launch system default browser registered in XDG
if command -v xdg-settings >/dev/null; then
    default_desktop=$(xdg-settings get default-web-browser 2>/dev/null || true)
    if [ -n "$default_desktop" ] && command -v gtk-launch >/dev/null; then
        exec gtk-launch "$default_desktop"
    fi
fi

# 3. Fallback search by known binary names
for b in brave-browser brave zen-browser zen firefox firefox-esr google-chrome-stable google-chrome chromium; do
    if command -v "$b" >/dev/null; then
        exec "$b"
    fi
done

notify-send -a "Browser" "Browser" "No web browser found on system" -u critical
