#!/bin/bash
# install.sh - Automated install script for akim-dotfiles (Arch Linux & Debian)

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

echo "=========================================================================="
echo " Starting installation of akim-dotfiles"
echo "=========================================================================="

TARGET_OS=""

# Parse manual flags if provided
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)
            TARGET_OS="arch"
            shift
            ;;
        --debian)
            TARGET_OS="debian"
            shift
            ;;
        --rollback)
            bash "$SCRIPT_DIR/install/rollback.sh"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--arch | --debian | --rollback]"
            exit 1
            ;;
    esac
done

# Auto-detect OS if not explicitly set
if [ -z "$TARGET_OS" ]; then
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "${ID:-}" in
            arch|endeavouros|manjaro|garuda|artix)
                TARGET_OS="arch"
                ;;
            debian|ubuntu|pop|linuxmint)
                TARGET_OS="debian"
                ;;
            *)
                if [ -n "${ID_LIKE:-}" ]; then
                    case "$ID_LIKE" in
                        *arch*) TARGET_OS="arch" ;;
                        *debian*) TARGET_OS="debian" ;;
                    esac
                fi
                ;;
        esac
    fi
fi

# Fallback to package manager detection
if [ -z "$TARGET_OS" ]; then
    if command -v pacman &>/dev/null; then
        TARGET_OS="arch"
    elif command -v apt-get &>/dev/null; then
        TARGET_OS="debian"
    else
        die "Could not automatically detect OS. Run with --arch or --debian."
    fi
fi

echo "--> Target platform detected: $TARGET_OS"

# Run OS-specific package installer
if [ "$TARGET_OS" = "arch" ]; then
    bash "$SCRIPT_DIR/install/arch.sh" || die "Arch Linux installation failed."
elif [ "$TARGET_OS" = "debian" ]; then
    bash "$SCRIPT_DIR/install/debian.sh" || die "Debian installation failed."
else
    die "Unsupported operating system: $TARGET_OS"
fi

# Run common dotfiles deployment and initial pywal setup
bash "$SCRIPT_DIR/install/common.sh" || die "Shared dotfiles deployment failed."

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
echo "   SUPER + Shift + T    -> Waybar theme selector"
echo "   SUPER + ALT + Right  -> Next wallpaper + theme update"
echo "   SUPER + ALT + Left   -> Previous wallpaper + theme update"
echo ""
echo " On Debian: Hyprland is available at the GDM login screen (gear icon)."
echo " On Arch:   SDDM is enabled with the akim theme."
echo "=========================================================================="
