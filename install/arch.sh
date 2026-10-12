#!/bin/bash
# install/arch.sh - Arch Linux package installer for akim-dotfiles
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================================="
echo " Starting Arch Linux Environment Preparation"
echo "=========================================================================="

ARCH_PKGS=(
    hyprland
    waybar
    kitty
    rofi-wayland
    wofi
    cliphist
    wl-clipboard
    grim
    slurp
    brightnessctl
    playerctl
    pipewire
    pipewire-pulse
    wireplumber
    xdg-desktop-portal
    xdg-desktop-portal-hyprland
    ttf-jetbrains-mono-nerd
    ttf-font-awesome
    papirus-icon-theme
    qt5ct
    qt6ct
    btop
    fastfetch
    chafa
    nautilus
    python-nautilus
    python-pillow
    python-pipx
    python-pywal
    blueman
    networkmanager
    zsh
    zsh-syntax-highlighting
    zsh-autosuggestions
    imagemagick
    swappy
    libnotify
    curl
    wget
    tar
    xz
    fontconfig
)

if command -v pacman &>/dev/null; then
    echo "--> Installing packages via pacman..."
    sudo pacman -S --needed --noconfirm "${ARCH_PKGS[@]}" 2>/dev/null || {
        echo "WARNING: Some packages could not be installed via pacman. Continuing..."
    }
fi

if command -v pipx &>/dev/null; then
    pipx ensurepath >/dev/null 2>&1 || true
    export PATH="$HOME/.local/bin:$PATH"
    pipx install pywal16 --force 2>/dev/null || true
    pipx install waypaper --force 2>/dev/null || true
fi

echo "=========================================================================="
echo " Arch Linux package installation complete."
echo "=========================================================================="
