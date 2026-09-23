#!/bin/bash
# install/common.sh - Shared configuration deployment for akim-dotfiles
# Used by both Arch Linux and Debian installation workflows.

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

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

backup_item() {
    local target="$1"
    if [ -e "$target" ] || [ -L "$target" ]; then
        local backup_path="${target}.backup-before-akim-dotfiles-${TIMESTAMP}"
        echo "--> Backing up $target to $backup_path"
        mv "$target" "$backup_path"
    fi
}

echo "=========================================================================="
echo " Deploying shared configuration files..."
echo "=========================================================================="

# 1. Base directories
echo "--> Creating target directories..."
mkdir -p "$HOME/.config"
mkdir -p "$HOME/.cache/wal"
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/share/themes"
mkdir -p "$HOME/.local/share/icons"
mkdir -p "$HOME/.local/share/fonts"
mkdir -p "$HOME/Pictures/wallpapers"
mkdir -p "$HOME/Pictures/Screenshots"

# 2. Cava + pywal16 integration
echo "--> Setting up Cava color theme integration with pywal16..."
mkdir -p "$HOME/.config/cava"
ln -sf "$HOME/.cache/wal/colors-cava" "$HOME/.config/cava/config"

# 3. Wallpapers & Avatar
REPO_WALLPAPERS_DIR="$REPO_ROOT/wallpapers"
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

if [ -f "$REPO_ROOT/assets/akim-avatar.png" ]; then
    echo "--> Installing hyprlock avatar..."
    cp "$REPO_ROOT/assets/akim-avatar.png" "$HOME/Pictures/akim-avatar.png"
fi

if [ -f "$TARGET_WALLPAPERS_DIR/image1.jpg" ]; then
    echo "--> Setting image1.jpg as current.jpg (symlink)..."
    ln -sf "$TARGET_WALLPAPERS_DIR/image1.jpg" "$TARGET_WALLPAPER"
elif [ ! -f "$TARGET_WALLPAPER" ]; then
    echo "--> Generating fallback background..."
    python3 -c "
from PIL import Image
img = Image.new('RGB', (1920, 1080), color='#1e1e2e')
img.save('$TARGET_WALLPAPER', 'JPEG')
" || warn "Failed to create fallback wallpaper"
fi

# 4. Oh My Zsh
if [ ! -f "$HOME/.oh-my-zsh/oh-my-zsh.sh" ]; then
    echo "--> Installing Oh My Zsh..."
    RUNZSH=no CHSH=no sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended \
        || warn "Oh My Zsh installation failed"
fi

if [ -f "$REPO_ROOT/omz-custom/themes/fishy.zsh-theme" ] && [ -d "$HOME/.oh-my-zsh/themes" ]; then
    echo "--> Installing custom fishy theme..."
    cp "$REPO_ROOT/omz-custom/themes/fishy.zsh-theme" "$HOME/.oh-my-zsh/themes/"
fi

if [ -n "$(command -v zsh 2>/dev/null)" ] && [ "$SHELL" != "$(command -v zsh)" ]; then
    echo "--> Setting zsh as default shell..."
    if sudo usermod -s "$(command -v zsh)" "$USER" 2>/dev/null; then
        echo "--> Default shell changed to zsh (effective after next login)."
    elif command -v chsh &>/dev/null && chsh -s "$(command -v zsh)" < /dev/null 2>/dev/null; then
        echo "--> Default shell changed to zsh (effective after next login)."
    else
        warn "Could not change default shell automatically. Run manually: chsh -s \$(command -v zsh)"
    fi
fi

# 5. Deploy configurations with safe backups
echo "--> Deploying .config files (with automatic backups)..."
cd "$REPO_ROOT" || die "Cannot change directory to $REPO_ROOT"

for item in .config/*; do
    [ -e "$item" ] || continue
    base_name=$(basename "$item")
    target_dir="$HOME/.config/$base_name"
    backup_item "$target_dir"
    cp -r "$item" "$HOME/.config/" || die "Failed to copy $item"
done

backup_item "$HOME/.zshrc"
cp "$REPO_ROOT/.zshrc" "$HOME/.zshrc" || die "Failed to copy .zshrc"

# 6. GTK Theme synchronization
sync_gtk_settings() {
    local settings theme icon search_dirs

    for settings in "$HOME/.config/gtk-3.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"; do
        [ -f "$settings" ] || continue

        search_dirs="$HOME/.themes $HOME/.local/share/themes /usr/share/themes"
        theme=$(find $search_dirs -maxdepth 1 -type d \( \
            -iname 'catppuccin*mocha*blue*' -o \
            -iname 'Catppuccin*Mocha*Blue*' -o \
            -iname 'Catppuccin-Mocha-Standard-Blue-Dark' \
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

    # Synchronize dark theme to root & system-wide GTK configs (for GParted, Synaptic, etc.)
    echo "--> Synchronizing GTK Dark Theme for root & administrative applications..."
    if command -v sudo &>/dev/null; then
        sudo mkdir -p /root/.config/gtk-3.0 /root/.config/gtk-4.0 /etc/gtk-3.0 /etc/gtk-4.0 2>/dev/null || true
        [ -f "$HOME/.config/gtk-3.0/settings.ini" ] && sudo cp "$HOME/.config/gtk-3.0/settings.ini" /root/.config/gtk-3.0/ 2>/dev/null || true
        [ -f "$HOME/.config/gtk-3.0/settings.ini" ] && sudo cp "$HOME/.config/gtk-3.0/settings.ini" /etc/gtk-3.0/ 2>/dev/null || true
        [ -f "$HOME/.config/gtk-4.0/settings.ini" ] && sudo cp "$HOME/.config/gtk-4.0/settings.ini" /root/.config/gtk-4.0/ 2>/dev/null || true
        [ -f "$HOME/.config/gtk-4.0/settings.ini" ] && sudo cp "$HOME/.config/gtk-4.0/settings.ini" /etc/gtk-4.0/ 2>/dev/null || true
        if [ -f "$HOME/.config/gtk-3.0/gtk.css" ]; then
            sudo cp "$HOME/.config/gtk-3.0/gtk.css" /root/.config/gtk-3.0/ 2>/dev/null || true
            sudo cp "$HOME/.config/gtk-3.0/gtk.css" /etc/gtk-3.0/ 2>/dev/null || true
        fi
        if [ -d "$HOME/.local/share/themes" ]; then
            sudo cp -rn "$HOME/.local/share/themes"/* /usr/share/themes/ 2>/dev/null || true
        fi
    fi

    # Set GNOME / XDG interface color-scheme to prefer-dark for portals and browsers
    if command -v gsettings &>/dev/null; then
        echo "--> Configuring system interface to prefer-dark via gsettings..."
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
        gsettings set org.gnome.desktop.interface gtk-theme 'catppuccin-mocha-blue-standard+default' 2>/dev/null || true
        gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark' 2>/dev/null || true
    fi
}
sync_gtk_settings

# 7. Kvantum Theme for Qt
echo "--> Setting up Kvantum theme for Qt applications..."
if [ ! -d "$HOME/.config/Kvantum/catppuccin-mocha-blue" ]; then
    git clone --depth 1 https://github.com/catppuccin/Kvantum.git /tmp/catppuccin-kvantum 2>/dev/null || warn "Failed to clone Kvantum Catppuccin theme"
    if [ -d "/tmp/catppuccin-kvantum/themes/catppuccin-mocha-blue" ]; then
        mkdir -p "$HOME/.config/Kvantum"
        cp -r /tmp/catppuccin-kvantum/themes/catppuccin-mocha-blue "$HOME/.config/Kvantum/" 2>/dev/null
    fi
    rm -rf /tmp/catppuccin-kvantum
fi
if command -v kvantummanager &>/dev/null; then
    kvantummanager --set catppuccin-mocha-blue 2>/dev/null || true
fi

# 8. Set execute permissions on all custom scripts
echo "--> Making custom scripts executable..."
chmod +x "$HOME/.config/hypr/scripts/"*.sh 2>/dev/null || true
chmod +x "$HOME/.config/hypr/scripts/"*.py 2>/dev/null || true
chmod +x "$HOME/.config/waybar/scripts/"*.sh 2>/dev/null || true
chmod +x "$HOME/.config/swaync/"*.sh 2>/dev/null || true
chmod +x "$HOME/.config/swaync/"*.py 2>/dev/null || true
chmod +x "$HOME/.config/waypaper/wallpaper_script.sh" 2>/dev/null || true

# 9. Generate dynamic pywal theme
echo "--> Generating initial color scheme from wallpaper..."
if [ -x "$HOME/.config/hypr/scripts/apply-pywal-theme.sh" ]; then
    "$HOME/.config/hypr/scripts/apply-pywal-theme.sh" "$TARGET_WALLPAPER" \
        || warn "Initial pywal theme generation failed — run: ~/.config/hypr/scripts/apply-pywal-theme.sh"
fi

# 10. Configure Discord desktop entry for Wayland screen sharing if installed
setup_discord_wayland() {
    mkdir -p "$HOME/.local/share/applications"
    if [ -f "/usr/share/applications/discord.desktop" ]; then
        echo "--> Configuring Discord desktop entry for Wayland screen sharing..."
        cp "/usr/share/applications/discord.desktop" "$HOME/.local/share/applications/"
        sed -i 's|Exec=discord|Exec=discord --enable-features=WebRTCPipeWireCapturer|g' "$HOME/.local/share/applications/discord.desktop"
    fi
}
setup_discord_wayland

echo "=========================================================================="
echo " Common configuration deployment complete."
echo "=========================================================================="
