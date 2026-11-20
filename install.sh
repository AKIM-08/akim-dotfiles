#!/bin/bash
# install.sh - Automated install script for akim-dotfiles (Debian)

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: run ./install.sh as your normal user, not with sudo (it asks for your password when needed)." >&2
    exit 1
fi

# Keep a log of everything (useful when something fails)
LOG="$HOME/.cache/akim-dotfiles-install.log"
mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1
echo "== $(date '+%F %T')  akim-dotfiles install"

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

# Verify and handle platform
if [ -f /etc/arch-release ] || command -v pacman &>/dev/null; then
    echo "--> Target platform verified: Arch Linux"
    if [ -f "$SCRIPT_DIR/install/arch.sh" ]; then
        bash "$SCRIPT_DIR/install/arch.sh" || die "Arch Linux package installation failed."
    fi
elif [ -f /etc/debian_version ] || command -v apt-get &>/dev/null; then
    echo "--> Target platform verified: Debian"
    bash "$SCRIPT_DIR/install/debian.sh" || die "Debian package installation failed."
else
    echo "--> Platform not specifically Debian/Arch; proceeding with shared configuration deployment..."
fi

# Run dotfiles deployment, font verification, and initial pywal setup
bash "$SCRIPT_DIR/install/common.sh" || die "Dotfiles deployment failed."

PICTURES_DIR=$(xdg-user-dir PICTURES 2>/dev/null)
{ [ -n "$PICTURES_DIR" ] && [ "$PICTURES_DIR" != "$HOME" ]; } || PICTURES_DIR="$HOME/Pictures"

echo "=========================================================================="
echo " Installation complete!"
echo ""
echo " Wallpapers: $(find "$PICTURES_DIR/wallpapers" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) ! -name 'current.jpg' 2>/dev/null | wc -l) images in $PICTURES_DIR/wallpapers"
echo " Log:        $LOG"
echo ""
echo " FIRST STEPS"
echo "   Log out, pick 'Hyprland' in the login screen's session menu, log in."
echo "   Super + H opens Settings (bar, wallpaper, lock screen, language, shortcuts...)."
echo "   Super + G lists every shortcut."
echo ""
echo " MAIN SHORTCUTS"
echo "   Super + Return       Terminal (kitty)"
echo "   Super + Q            App launcher"
echo "   Super + F            Files"
echo "   Super + B            Web browser"
echo "   Super + A            Close the window"
echo "   Super + W            Wallpapers (the whole desktop takes its colors)"
echo "   Super + Alt + ← / →  Previous / next wallpaper"
echo "   Super + N            Quick panel (music, Wi-Fi, Bluetooth, sliders)"
echo "   Super + Shift + N    Notifications"
echo "   Super + H            Settings"
echo "   Super + Shift + T    Bar theme"
echo "   Super + V            Clipboard history"
echo "   Super + P            Screenshot menu (Shift: region, Alt: full screen)"
echo "   Super + L            Lock"
echo "   Super + Escape       Power menu"
echo "=========================================================================="
