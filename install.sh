#!/bin/bash
# install.sh - Automated install script for Arch Linux + Hyprland

set -o pipefail

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

echo "=========================================================================="
echo " Starting installation of akim-dotfiles"
echo "=========================================================================="

# 1. System Language Config (English US)
echo "--> Configuring locale system to en_US.UTF-8..."
if ! grep -q "^en_US.UTF-8 UTF-8" /etc/locale.gen; then
    echo "en_US.UTF-8 UTF-8" | sudo tee -a /etc/locale.gen > /dev/null
fi
sudo locale-gen || die "locale-gen failed"
echo "LANG=en_US.UTF-8" | sudo tee /etc/locale.conf > /dev/null
export LANG=en_US.UTF-8

# 2. Core packages (required for the dotfiles to work)
echo "--> Installing core dependencies..."
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
    wlogout \
    gtk3 \
    papirus-icon-theme \
    libnotify \
    nautilus \
    pipewire \
    wireplumber \
    xdg-user-dirs \
    hyprland \
    hyprpaper \
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
    zsh-syntax-highlighting \
    zsh-autosuggestions \
    imagemagick \
    || die "Core package installation failed"

# 2b. Optional applications (non-blocking)
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

# 3. Install yay (AUR helper)
if ! command -v yay &> /dev/null; then
    echo "--> Installing yay (AUR helper)..."
    git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin || die "Failed to clone yay-bin"
    (cd /tmp/yay-bin && makepkg -si --noconfirm) || die "Failed to install yay"
    rm -rf /tmp/yay-bin
fi

# 4. AUR packages required by the dotfiles
echo "--> Installing required AUR packages..."
yay -S --needed --noconfirm \
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
        || warn "Could not apply Catppuccin Mocha Papirus folder color (run: papirus-folders -l | grep mocha)"
else
    warn "papirus-folders not found — icon folder colors not applied"
fi

# 5. Optional AUR packages
run_optional "Installing optional AUR packages" \
    yay -S --needed --noconfirm \
        brave-bin \
        spotify \
        pipes.sh \
        tty-clock

# 6. Cava + pywal16 integration
echo "--> Setting up Cava color theme integration with pywal16..."
mkdir -p "$HOME/.config/cava"
ln -sf "$HOME/.cache/wal/colors-cava" "$HOME/.config/cava/config"

# 7. Directories and wallpapers
echo "--> Creating configuration and cache directories..."
mkdir -p "$HOME/.config"
mkdir -p "$HOME/.cache/wal"
mkdir -p "$HOME/Pictures/wallpapers"
mkdir -p "$HOME/Pictures/Screenshots"

REPO_WALLPAPERS_DIR="wallpapers"
TARGET_WALLPAPERS_DIR="$HOME/Pictures/wallpapers"
TARGET_WALLPAPER="$TARGET_WALLPAPERS_DIR/current.jpg"

if [ -d "$REPO_WALLPAPERS_DIR" ]; then
    echo "--> Copying wallpapers from repo to $TARGET_WALLPAPERS_DIR..."
    shopt -s nullglob
    for wallpaper in "$REPO_WALLPAPERS_DIR"/image*.*; do
        cp "$wallpaper" "$TARGET_WALLPAPERS_DIR/"
    done
    shopt -u nullglob
fi

if [ -f "assets/akim-avatar.png" ]; then
    echo "--> Installing hyprlock avatar..."
    cp assets/akim-avatar.png "$HOME/Pictures/akim-avatar.png"
fi

if [ -f "$TARGET_WALLPAPERS_DIR/image1.jpg" ]; then
    echo "--> Setting image1.jpg as current.jpg (active wallpaper)..."
    cp "$TARGET_WALLPAPERS_DIR/image1.jpg" "$TARGET_WALLPAPER"
elif [ ! -f "$TARGET_WALLPAPER" ]; then
    echo "--> Generating fallback background..."
    python3 -c "
from PIL import Image
img = Image.new('RGB', (1920, 1080), color='#1e1e2e')
img.save('$TARGET_WALLPAPER', 'JPEG')
" || die "Failed to create fallback wallpaper"
fi

# 8. Oh My Zsh
if [ ! -f "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]; then
    echo "--> Installing Oh My Zsh..."
    RUNZSH=no CHSH=no sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended \
        || die "Oh My Zsh installation failed"
fi

if [ ! -f "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]; then
    die "Oh My Zsh is required but missing at ~/.oh-my-zsh"
fi

if [ -f "omz-custom/themes/fishy.zsh-theme" ]; then
    echo "--> Installing custom fishy theme..."
    cp omz-custom/themes/fishy.zsh-theme "$HOME/.oh-my-zsh/themes/"
fi

if [ "$SHELL" != "$(command -v zsh)" ]; then
    echo "--> Setting zsh as default shell..."
    if chsh -s "$(command -v zsh)" 2>/dev/null; then
        echo "--> Default shell changed to zsh (effective after next login)."
    else
        warn "Could not change default shell. Run manually: chsh -s \$(command -v zsh)"
    fi
fi

# 9. Deploy configurations
echo "--> Copying configurations to target directories..."
cp -r .config/* "$HOME/.config/" || die "Failed to copy .config"
cp .zshrc "$HOME/.zshrc" || die "Failed to copy .zshrc"

# 10. wlogout power menu
setup_wlogout() {
    echo "--> Setting up wlogout power menu..."
    command -v wlogout &>/dev/null || die "wlogout is not installed — run: sudo pacman -S wlogout"

    local wdir="$HOME/.config/wlogout"
    if [ ! -f "$wdir/layout" ]; then
        warn "wlogout layout missing at $wdir/layout — copying from system defaults if available"
        if [ -f /etc/wlogout/layout ]; then
            mkdir -p "$wdir"
            cp /etc/wlogout/layout "$wdir/layout"
        fi
    fi

    if [ ! -f "$wdir/style.css" ] && [ -f /etc/wlogout/style.css ]; then
        cp /etc/wlogout/style.css "$wdir/style.css"
        warn "Copied default wlogout style.css — re-run install or restore repo config for pywal styling"
    fi

    echo "--> wlogout ready (Super+Shift+E, layer-shell protocol)"
}
setup_wlogout

# 11. Sync GTK theme names with installed Catppuccin Mocha
sync_gtk_settings() {
    local settings theme icon search_dirs

    for settings in "$HOME/.config/gtk-3.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"; do
        [ -f "$settings" ] || continue

        search_dirs="$HOME/.themes $HOME/.local/share/themes /usr/share/themes"
        theme=$(find $search_dirs -maxdepth 1 -type d \( \
            -iname 'catppuccin*mocha*blue*' -o \
            -iname 'Catppuccin*Mocha*Blue*' \
            \) 2>/dev/null | head -1)
        if [ -z "$theme" ]; then
            theme=$(find $search_dirs -maxdepth 1 -type d -iname '*catppuccin*mocha*' 2>/dev/null | head -1)
        fi
        if [ -n "$theme" ]; then
            theme=$(basename "$theme")
            sed -i "s/^gtk-theme-name=.*/gtk-theme-name=${theme}/" "$settings"
            echo "--> GTK theme set to: $theme ($settings)"
        else
            warn "Catppuccin Mocha GTK theme not found — check $settings manually"
        fi

        if [ "$settings" = "$HOME/.config/gtk-3.0/settings.ini" ]; then
            icon="Papirus-Dark"
            if [ -d "/usr/share/icons/$icon" ] || [ -d "$HOME/.icons/$icon" ] || [ -d "$HOME/.local/share/icons/$icon" ]; then
                sed -i "s/^gtk-icon-theme-name=.*/gtk-icon-theme-name=${icon}/" "$settings"
                echo "--> GTK icon theme set to: $icon"
            else
                warn "Papirus-Dark icon theme not found — check gtk-3.0/settings.ini manually"
            fi
        fi
    done
}
sync_gtk_settings

# 12. Make scripts executable
echo "--> Making scripts executable..."
chmod +x "$HOME/.config/hypr/scripts/screenshot.sh"
chmod +x "$HOME/.config/hypr/scripts/switch-wallpaper.sh"
chmod +x "$HOME/.config/hypr/scripts/apply-pywal-theme.sh"
chmod +x "$HOME/.config/hypr/scripts/pywal-fallback.py"
chmod +x "$HOME/.config/waybar/scripts/"*.sh
chmod +x "$HOME/.config/swaync/refresh.sh"
chmod +x "$HOME/.config/waypaper/wallpaper_script.sh"
chmod +x "$HOME/.config/wlogout/hibernate.sh"

# 13. Generate pywal16 color scheme from wallpaper (dynamic theme)
echo "--> Generating initial color scheme from wallpaper..."
"$HOME/.config/hypr/scripts/apply-pywal-theme.sh" "$TARGET_WALLPAPER" \
    || warn "Theme generation failed — run: ~/.config/hypr/scripts/apply-pywal-theme.sh"

echo "=========================================================================="
echo " Installation complete!"
echo ""
echo " Wallpapers installed: $(find "$HOME/Pictures/wallpapers" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) ! -name 'current.jpg' 2>/dev/null | wc -l) images"
echo " Default wallpaper: current.jpg"
echo ""
echo " KEY BINDINGS:"
echo "   SUPER + Return       -> Open terminal (Kitty)"
echo "   SUPER + Q            -> Close active window"
echo "   SUPER + A            -> App launcher (Rofi)"
echo "   SUPER + V            -> Clipboard history"
echo "   SUPER + N            -> Notification center"
echo "   SUPER + Shift + E    -> Power menu (wlogout)"
echo "   SUPER + Shift + T    -> Waybar theme selector"
echo "   SUPER + ALT + Right  -> Next wallpaper + theme update"
echo "   SUPER + ALT + Left   -> Previous wallpaper + theme update"
echo ""
echo " Optional: yay -S pywal-discord  (Discord theme sync with pywal16)"
echo ""
echo " Please run 'sudo reboot' to launch your new system."
echo "=========================================================================="
