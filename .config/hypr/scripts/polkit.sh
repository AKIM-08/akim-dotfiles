#!/usr/bin/env bash
# polkit.sh - Start PolicyKit authentication agent for Hyprland
# Ensures GUI apps requiring elevated/root privileges (GParted, Synaptic, etc.) prompt for password.

# Authorize local root user to connect to XWayland display server (e.g. for GParted, Synaptic)
if command -v xhost &>/dev/null; then
    xhost +SI:localuser:root >/dev/null 2>&1 || true
fi

# Prevent multiple agents running simultaneously
if pgrep -f "polkit.*agent" >/dev/null || pgrep -x lxpolkit >/dev/null; then
    exit 0
fi

# List of known polkit agent paths (Debian, Arch, Fedora)
AGENTS=(
    "/usr/lib/mate-polkit/polkit-mate-authentication-agent-1"
    "/usr/libexec/polkit-mate-authentication-agent-1"
    "/usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1"
    "/usr/libexec/polkit-gnome-authentication-agent-1"
    "/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1"
    "/usr/bin/lxpolkit"
    "/usr/lib/hyprpolkitagent"
    "/usr/libexec/hyprpolkitagent"
    "/usr/lib/x86_64-linux-gnu/libexec/polkit-gnome-authentication-agent-1"
    "/usr/lib/polkit-kde-authentication-agent-1"
    "/usr/lib/x86_64-linux-gnu/libexec/polkit-kde-authentication-agent-1"
    "/usr/bin/lxqt-policykit-agent"
)

for agent in "${AGENTS[@]}"; do
    if [ -x "$agent" ]; then
        exec "$agent"
    fi
done

# Fallback dynamic discovery in standard library directories
found=$(find /usr/lib* /usr/libexec -name "*polkit*authentication-agent*" -type f -perm /111 2>/dev/null | head -n 1)
if [ -n "$found" ] && [ -x "$found" ]; then
    exec "$found"
fi

echo "WARNING: No PolicyKit authentication agent executable found on the system." >&2
