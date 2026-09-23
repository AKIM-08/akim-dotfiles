#!/bin/bash
# install/arch.sh - Arch Linux package installation layer for akim-dotfiles

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

warn() {
    echo "WARNING: $*" >&2
}

run_optional() {
    echo "--> $1"
    shift
    "$@" || warn "$1 failed (continuing)"
}

if ! command -v pacman &>/dev/null; then
    die "pacman not found — this script requires Arch Linux."
fi

echo "=========================================================================="
echo " Arch Linux Package Installation"
echo "=========================================================================="

# 1. System Language Config (en_US.UTF-8)
echo "--> Configuring locale system to en_US.UTF-8..."
if ! grep -q "^en_US.UTF-8 UTF-8" /etc/locale.gen; then
    echo "en_US.UTF-8 UTF-8" | sudo tee -a /etc/locale.gen > /dev/null
fi
sudo locale-gen || die "locale-gen failed"
echo "LANG=en_US.UTF-8" | sudo tee /etc/locale.conf > /dev/null
export LANG=en_US.UTF-8

# 2. Core dependencies
echo "--> Installing core Arch dependencies..."
sudo pacman -Syu --needed --noconfirm \
    base-devel \
    git \
    zsh \
    kitty \
    waybar \
    rofi \
    wofi \
    networkmanager \
    hypridle \
    hyprlock \
    gtk3 \
    papirus-icon-theme \
    libnotify \
    nautilus \
    pipewire \
    pipewire-pulse \
    wireplumber \
    xdg-desktop-portal \
    xdg-desktop-portal-hyprland \
    polkit-gnome \
    xorg-xhost \
    bluez \
    btop \
    xdg-user-dirs \
    hyprland \
    awww \
    sddm \
    qt5-quickcontrols2 \
    qt5-graphicaleffects \
    qt5-svg \
    qt5-declarative \
    qt6-wayland \
    qt6-multimedia-ffmpeg \
    qt6-declarative \
    qt6-quickcontrols2 \
    qt5ct \
    qt6ct \
    kvantum \
    swaync \
    cliphist \
    wl-clipboard \
    python \
    python-pillow \
    pavucontrol \
    grim \
    slurp \
    playerctl \
    brightnessctl \
    ttf-jetbrains-mono-nerd \
    otf-font-awesome \
    blueman \
    pacman-contrib \
    hyprpicker \
    libpulse \
    fastfetch \
    chafa \
    zsh-syntax-highlighting \
    zsh-autosuggestions \
    imagemagick \
    luajit \
    power-profiles-daemon \
    swappy \
    wf-recorder \
    ffmpeg \
    || die "Core package installation failed"

# 2b. Optional applications
run_optional "Installing optional applications" \
    sudo pacman -S --needed --noconfirm \
        firefox \
        discord \
        telegram-desktop \
        code \
        libreoffice-fresh \
        vlc \
        obs-studio \
        cava \
        cmatrix

xdg-user-dirs-update

sudo systemctl enable --now NetworkManager 2>/dev/null || warn "Could not enable NetworkManager"
sudo systemctl enable --now bluetooth 2>/dev/null || warn "Could not enable bluetooth (no adapter?)"

# 3. Install yay (AUR helper)
if ! command -v yay &> /dev/null; then
    echo "--> Installing yay (AUR helper)..."
    git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin || die "Failed to clone yay-bin"
    (cd /tmp/yay-bin && makepkg -si --noconfirm) || die "Failed to install yay"
    rm -rf /tmp/yay-bin
fi

# 4. AUR packages
echo "--> Installing required AUR packages..."
yay -S --needed --noconfirm \
    snmenu \
    python-pywal16 \
    catppuccin-gtk-theme-mocha \
    papirus-folders-catppuccin-git \
    nordzy-cursors \
    waypaper \
    || die "Required AUR package installation failed"

# Apply Catppuccin Mocha folder colors to Papirus icons
if command -v papirus-folders &>/dev/null; then
    echo "--> Applying Catppuccin Mocha colors to Papirus icon folders..."
    papirus-folders -C cat-mocha-blue -S --once 2>/dev/null \
        || papirus-folders -C cat-mocha-mauve -S --once 2>/dev/null \
        || warn "Could not apply Catppuccin Mocha Papirus folder color"
fi

# 5. Optional AUR packages
run_optional "Installing optional AUR packages" \
    yay -S --needed --noconfirm \
        brave-bin \
        spotify \
        pipes.sh \
        tty-clock \
        catppuccin-sddm-corners-mocha

# 6. SDDM setup for Arch
setup_sddm() {
    echo "--> Setting up SDDM login screen..."

    if [ -f "$HOME/Pictures/akim-avatar.png" ]; then
        cp "$HOME/Pictures/akim-avatar.png" "$HOME/.face" 2>/dev/null || true
        cp "$HOME/Pictures/akim-avatar.png" "$HOME/.face.icon" 2>/dev/null || true
    fi

    local theme="akim"
    if [ -d "$REPO_ROOT/sddm/akim" ]; then
        echo "--> Installing custom SDDM theme (akim)..."
        sudo mkdir -p "/usr/share/sddm/themes/$theme"
        sudo cp -r "$REPO_ROOT/sddm/akim/"* "/usr/share/sddm/themes/$theme/"
    fi

    sudo mkdir -p /etc/sddm.conf.d
    if [ -f "$REPO_ROOT/sddm/akim-dotfiles.conf" ]; then
        sudo cp "$REPO_ROOT/sddm/akim-dotfiles.conf" /etc/sddm.conf.d/akim-dotfiles.conf
    fi

    sudo systemctl enable sddm.service 2>/dev/null || warn "Could not enable sddm.service"
}
setup_sddm

echo "=========================================================================="
echo " Arch Linux package installation complete."
echo "=========================================================================="
