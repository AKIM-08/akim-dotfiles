#!/bin/bash
# install.sh - Automated install script for akim-dotfiles (Debian)

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

echo "=========================================================================="
echo " Starting installation of akim-dotfiles for Debian"
echo "=========================================================================="

# Parse flags if provided
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rollback)
            bash "$SCRIPT_DIR/install/rollback.sh"
            exit 0
            ;;
        -h|--help)
            echo "Usage: $0 [--rollback | --help]"
            echo "Installs akim-dotfiles configured specifically for Debian (Trixie, Testing, Sid, Bookworm)."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--rollback | --help]"
            exit 1
            ;;
    esac
done

# Verify Debian platform
if [ ! -f /etc/debian_version ] && ! command -v apt-get &>/dev/null; then
    die "This configuration is dedicated exclusively to Debian (or Debian-based systems with APT)."
fi

echo "--> Target platform verified: Debian"

# Run Debian package & dependency layer installer
bash "$SCRIPT_DIR/install/debian.sh" || die "Debian package installation failed."

# Run dotfiles deployment and initial pywal setup
bash "$SCRIPT_DIR/install/common.sh" || die "Dotfiles deployment failed."

echo "=========================================================================="
echo " Installation complete!"
echo ""
echo " Wallpapers installed: $(find "$HOME/Pictures/wallpapers" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) ! -name 'current.jpg' 2>/dev/null | wc -l) images"
echo " Default wallpaper: current.jpg"
echo ""
echo " KEY BINDINGS:"
echo "   SUPER + Return       -> Open terminal (Kitty)"
echo "   SUPER + Q            -> App launcher (Rofi, toggle)"
echo "   SUPER + G            -> Shortcuts cheatsheet (Rofi toggle)"
echo "   SUPER + A            -> Close active window"
echo "   SUPER + V            -> Clipboard history (toggle)"
echo "   SUPER + B            -> Web browser"
echo "   SUPER + P            -> Screenshot menu (Rofi)"
echo "   SUPER + SHIFT + P    -> Screenshot (region)"
echo "   SUPER + ALT + P      -> Screenshot (full screen)"
echo "   SUPER + S            -> Scratchpad (toggle view)"
echo "   SUPER + SHIFT + S    -> Scratchpad (toggle send/remove active window)"
echo "   SUPER + Escape       -> Power menu (snmenu)"
echo "   SUPER + N            -> Notification center"
echo "   SUPER + Shift + T    -> Waybar theme selector (toggle)"
echo "   SUPER + ALT + Right  -> Next wallpaper + theme update"
echo "   SUPER + ALT + Left   -> Previous wallpaper + theme update"
echo ""
echo " SESSION ACCESS:"
echo "   Hyprland is registered with GDM / your display manager."
echo "   Log out or reboot, then select 'Hyprland' from the session gear menu."
echo "=========================================================================="
