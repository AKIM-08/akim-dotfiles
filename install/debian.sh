#!/bin/bash
# install/debian.sh - Debian package & integration installer for akim-dotfiles
# Preserves GNOME, GDM, and dual-boot configurations.

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

if [ ! -f /etc/debian_version ] && ! command -v apt-get &>/dev/null; then
    die "This script requires Debian or a Debian-based Linux distribution."
fi

echo "=========================================================================="
echo " Starting Debian Environment Inspection & Preparation"
echo "=========================================================================="

# 1. Inspect Debian Environment
echo "--> Detecting system information..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DEBIAN_VERSION="${VERSION_CODENAME:-$VERSION_ID}"
    echo "    Distribution: $PRETTY_NAME ($DEBIAN_VERSION)"
fi
echo "    Kernel:       $(uname -r)"
echo "    Architecture: $(uname -m)"

# Check GPU
GPU_INFO=$(lspci 2>/dev/null | grep -Ei 'vga|3d|display' || echo "Unknown GPU")
echo "    GPU:          $GPU_INFO"

# Check active Display Manager (Ensuring GDM preservation)
ACTIVE_DM=""
if [ -f /etc/X11/default-display-manager ]; then
    ACTIVE_DM=$(basename "$(cat /etc/X11/default-display-manager 2>/dev/null)")
fi
echo "    Display Mgr:  ${ACTIVE_DM:-GDM (Default)}"
echo "    Desktop Env:  ${XDG_CURRENT_DESKTOP:-GNOME (or non-graphical)}"

echo ""
echo "NOTE: GNOME and GDM will remain fully intact and functional."
echo "      Hyprland will be added as a selectable session in GDM."
echo "=========================================================================="

# 2. Update APT repositories
echo "--> Updating APT package lists..."
sudo apt-get update || die "apt-get update failed. Please check your network and repositories."

# 3. Base & Core Build Utilities
echo "--> Installing build essentials and tools..."
sudo apt-get install -y \
    build-essential \
    cargo \
    git \
    curl \
    wget \
    zsh \
    pipx \
    python3-pip \
    python3-pil \
    python3-pyqt5 \
    python3-pyqt6 \
    libnotify-bin \
    pkg-config \
    libglib2.0-bin \
    unzip \
    tar \
    xz-utils \
    || die "Failed to install base build tools."

pipx ensurepath >/dev/null 2>&1 || true
export PATH="$HOME/.local/bin:$PATH"

# 4. Hyprland & Wayland Ecosystem Packages
echo "--> Installing Hyprland and Wayland ecosystem packages from APT..."
APT_CORE_PKGS=(
    kitty
    waybar
    rofi
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
    fonts-jetbrains-mono
    fonts-font-awesome
    papirus-icon-theme
    qt5ct
    qt6ct
    btop
    fastfetch
    nautilus
    blueman
    network-manager
    zsh-syntax-highlighting
    zsh-autosuggestions
    imagemagick
    policykit-1-gnome
)

# 2b. Enable trixie-backports (required for Hyprland packages)
echo "--> Enabling trixie-backports repository..."
BACKPORTS_FILE="/etc/apt/sources.list.d/backports.list"
if ! grep -q "trixie-backports" /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null; then
    echo "deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware" | sudo tee "$BACKPORTS_FILE" > /dev/null
    sudo apt-get update || die "apt-get update failed after adding backports."
    echo "    ✓ trixie-backports added"
else
    echo "    ✓ trixie-backports already configured"
fi

# Optional packages available in standard APT
APT_EXTRA_PKGS=(
    sway-notification-center
    qt5-style-kvantum
    qt6-style-kvantum
    pavucontrol
    bluez
)

# Hyprland packages from backports (REQUIRED, not optional)
BACKPORTS_PKGS=(
    hyprland
    hyprlock
    hypridle
    xdg-desktop-portal-hyprland
)

echo "--> Installing Hyprland packages from trixie-backports..."
for pkg in "${BACKPORTS_PKGS[@]}"; do
    sudo apt-get install -y -t trixie-backports "$pkg" || echo "WARNING: Failed to install $pkg from backports"
done

for pkg in "${APT_CORE_PKGS[@]}"; do
    run_optional "Installing $pkg" sudo apt-get install -y "$pkg"
done

for pkg in "${APT_EXTRA_PKGS[@]}"; do
    run_optional "Installing (extra/trixie) $pkg" sudo apt-get install -y "$pkg"
done

# If SwayNC package name is 'swaync' instead of 'sway-notification-center'
if ! command -v swaync &>/dev/null; then
    sudo apt-get install -y swaync 2>/dev/null || true
fi

# 5. Non-Packaged / AUR Tools Setup

## 5a. Nerd Fonts (JetBrainsMono Nerd Font)
echo "--> Setting up JetBrainsMono Nerd Font icons..."
mkdir -p "$HOME/.local/share/fonts"
if ! fc-list : family | grep -qi "JetBrainsMono Nerd Font"; then
    echo "    Downloading JetBrainsMono Nerd Font symbols..."
    mkdir -p /tmp/jbm-nerd-font
    wget -q --show-progress -O /tmp/jbm-nerd-font/JetBrainsMono.tar.xz \
        https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.tar.xz 2>/dev/null \
        && tar -xf /tmp/jbm-nerd-font/JetBrainsMono.tar.xz -C "$HOME/.local/share/fonts/" 2>/dev/null \
        && rm -rf /tmp/jbm-nerd-font \
        && fc-cache -fv "$HOME/.local/share/fonts" >/dev/null 2>&1 \
        || warn "Could not download JetBrainsMono Nerd Font archive"
fi

## 5b. Python tools (pywal16 & waypaper via pipx)
echo "--> Installing Python utilities (pywal16, waypaper)..."
pipx install pywal16 --force 2>/dev/null || pipx install pywal --force 2>/dev/null || warn "Could not install pywal via pipx (fallback python script is bundled)"
pipx install waypaper --force 2>/dev/null || warn "Could not install waypaper via pipx"

## 5c. Catppuccin Mocha GTK Theme
echo "--> Installing Catppuccin Mocha GTK Theme..."
mkdir -p "$HOME/.local/share/themes"
if [ ! -d "$HOME/.local/share/themes/catppuccin-mocha-blue-standard+default" ] && [ ! -d "/usr/share/themes/catppuccin-mocha-blue-standard+default" ]; then
    echo "    Downloading and applying Catppuccin Mocha GTK theme..."
    mkdir -p /tmp/catppuccin-gtk
    if curl -LsS "https://raw.githubusercontent.com/catppuccin/gtk/main/install.py" -o /tmp/catppuccin-gtk/install.py 2>/dev/null; then
        (cd /tmp/catppuccin-gtk && python3 install.py mocha blue -d "$HOME/.local/share/themes") 2>/dev/null || warn "Catppuccin GTK install.py failed"
    fi
    rm -rf /tmp/catppuccin-gtk
fi

## 5d. Nordzy Cursors
echo "--> Installing Nordzy Cursors..."
mkdir -p "$HOME/.local/share/icons"
if [ ! -d "$HOME/.local/share/icons/Nordzy-cursors" ] && [ ! -d "/usr/share/icons/Nordzy-cursors" ]; then
    echo "    Downloading Nordzy Cursors..."
    mkdir -p /tmp/nordzy
    wget -q -O /tmp/nordzy/Nordzy-cursors.tar.gz \
        https://github.com/alvatip/Nordzy-cursors/releases/latest/download/Nordzy-cursors.tar.gz 2>/dev/null \
        && tar -xzf /tmp/nordzy/Nordzy-cursors.tar.gz -C "$HOME/.local/share/icons/" 2>/dev/null \
        && rm -rf /tmp/nordzy \
        || warn "Could not download Nordzy cursors archive"
fi

## 5e. papirus-folders
echo "--> Setting up papirus-folders for Catppuccin icon coloring..."
if ! command -v papirus-folders &>/dev/null; then
    mkdir -p /tmp/papirus-folders
    git clone --depth 1 https://github.com/PapirusDevelopmentTeam/papirus-folders.git /tmp/papirus-folders 2>/dev/null \
        && sudo cp /tmp/papirus-folders/papirus-folders /usr/local/bin/ \
        && sudo chmod +x /usr/local/bin/papirus-folders \
        && rm -rf /tmp/papirus-folders 2>/dev/null \
        || warn "Could not install papirus-folders script"
fi
if command -v papirus-folders &>/dev/null; then
    papirus-folders -C blue --theme Papirus-Dark 2>/dev/null || true
fi

## 5f. Rust tools: awww (animated wallpaper daemon) & snmenu (radial power menu)
echo "--> Checking Rust tools (awww, snmenu)..."
mkdir -p "$HOME/.local/bin"

install_rust_git() {
    local repo_url="$1"
    shift
    local packages=("$@")
    if command -v cargo &>/dev/null; then
        for pkg in "${packages[@]}"; do
            if ! command -v "$pkg" &>/dev/null && [ ! -x "$HOME/.local/bin/$pkg" ]; then
                echo "    Installing $pkg from $repo_url..."
                cargo install --git "$repo_url" "$pkg" --root "$HOME/.local" 2>/dev/null || warn "Failed to install $pkg"
            fi
        done
    else
        warn "Rust 'cargo' not found. If you wish to build packages from source: sudo apt install cargo liblz4-dev pkg-config"
    fi
}

install_rust_git "https://codeberg.org/LGFae/awww.git" "awww" "awww-daemon"

# 6. Wayland Session Registration for GDM & PAM Configuration
echo "--> Ensuring Hyprland Wayland session is registered with GDM..."
sudo mkdir -p /usr/share/wayland-sessions
if [ ! -f /usr/share/wayland-sessions/hyprland.desktop ]; then
    echo "    Creating /usr/share/wayland-sessions/hyprland.desktop..."
    sudo tee /usr/share/wayland-sessions/hyprland.desktop > /dev/null << 'EOF'
[Desktop Entry]
Name=Hyprland
Comment=An intelligent dynamic tiling Wayland compositor
Exec=Hyprland
Type=Application
DesktopNames=Hyprland
Keywords=tiling;wm;windowmanager;window;manager;
EOF
fi

# 7. Configure PAM for hyprlock (essential for Debian authentication)
echo "--> Configuring PAM for hyprlock..."
sudo tee /etc/pam.d/hyprlock > /dev/null << 'EOF'
#%PAM-1.0
@include common-auth
@include common-account
@include common-password
@include common-session
EOF

# 8. Add user to input and video groups (for keyboard/mouse access under Wayland)
echo "--> Ensuring user is in input and video groups..."
sudo usermod -aG input,video "$USER" 2>/dev/null || true

# 9. Ensure only GDM is active (disable SDDM if previously enabled)
echo "--> Ensuring GDM is active and disabling any conflicting SDDM..."
sudo systemctl disable sddm 2>/dev/null || true

echo "=========================================================================="
echo " Debian package and dependency layer installation complete."
echo "=========================================================================="
