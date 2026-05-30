#!/bin/bash
# Installe le thème SDDM akim dans /usr/share/sddm/themes/ (pas le dossier git)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
THEME_NAME="akim"
THEME_DIR="/usr/share/sddm/themes/${THEME_NAME}"
SRC="${REPO_ROOT}/sddm/${THEME_NAME}"
WALLPAPER="${HOME}/Pictures/wallpapers/current.jpg"

if [ ! -d "$SRC" ] || [ ! -f "$SRC/Main.qml" ]; then
    echo "ERROR: Missing ${SRC}/Main.qml — run from akim-dotfiles repo." >&2
    exit 1
fi

echo "--> Installing SDDM theme to ${THEME_DIR}..."
sudo mkdir -p "$THEME_DIR"
sudo cp -r "$SRC/"* "$THEME_DIR/"

if [ -f "$WALLPAPER" ]; then
    sudo cp -L "$WALLPAPER" "${THEME_DIR}/background.jpg" 2>/dev/null \
        || sudo cp "$WALLPAPER" "${THEME_DIR}/background.jpg"
fi

echo "--> Writing /etc/sddm.conf.d/akim-dotfiles.conf (Current=${THEME_NAME})..."
sudo mkdir -p /etc/sddm.conf.d
sudo cp "${REPO_ROOT}/sddm/akim-dotfiles.conf" /etc/sddm.conf.d/akim-dotfiles.conf

# Supprimer les configs qui pointent par erreur vers le clone git
for conf in /etc/sddm.conf.d/*.conf; do
    [ -f "$conf" ] || continue
    if grep -qE 'akim-dotfiles/sddm|/home/.*/akim-dotfiles' "$conf" 2>/dev/null; then
        echo "--> Removing invalid theme path in $conf"
        sudo rm -f "$conf"
    fi
done
sudo rm -f /etc/sddm.conf.d/akim-dotfiles-theme.conf 2>/dev/null || true

if command -v sddm-greeter &>/dev/null; then
    echo "--> Testing theme..."
    sddm-greeter --test-mode --theme "$THEME_NAME" || {
        echo "WARNING: sddm-greeter test failed — see: journalctl -u sddm -b"
        exit 1
    }
fi

echo "OK — SDDM theme installed. Reboot or: sudo systemctl restart sddm"
