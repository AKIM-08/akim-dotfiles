#!/bin/bash
# Installe le thème SDDM akim dans /usr/share/sddm/themes/ (pas le dossier git)

set -euo pipefail

THEME_NAME="akim"
THEME_DIR="/usr/share/sddm/themes/${THEME_NAME}"
WALLPAPER="${HOME}/Pictures/wallpapers/current.jpg"

want_path="sddm/${THEME_NAME}/Main.qml"

is_repo_root() { [[ -f "$1/$want_path" ]]; }

find_upwards() {
    local d="$1"
    while [[ -n "$d" && "$d" != "/" ]]; do
        if is_repo_root "$d"; then
            printf '%s\n' "$d"
            return 0
        fi
        d="$(cd "$d/.." && pwd)"
    done
    return 1
}

REPO_ROOT="${AKIM_DOTFILES_REPO:-}"

if [[ -z "${REPO_ROOT}" ]] && command -v git >/dev/null 2>&1; then
    REPO_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)"
fi

if [[ -z "${REPO_ROOT}" ]]; then
    REPO_ROOT="$(find_upwards "$PWD" 2>/dev/null || true)"
fi

if [[ -z "${REPO_ROOT}" ]]; then
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(find_upwards "$script_dir" 2>/dev/null || true)"
fi

# Chemins courants si le script est lancé hors du repo (ex. depuis ~/.config/hypr/scripts/)
for fallback_path in \
    "${HOME}/akim-dotfiles" \
    "${HOME}/Downloads/akim-dotfiles" \
    "${HOME}/dotfiles" \
    "${HOME}/Documents/akim-dotfiles"; do
    if [[ -z "${REPO_ROOT}" ]] && is_repo_root "${fallback_path}"; then
        REPO_ROOT="${fallback_path}"
        break
    fi
done

SRC="${REPO_ROOT}/sddm/${THEME_NAME}"

if [ ! -d "$SRC" ] || [ ! -f "$SRC/Main.qml" ]; then
    echo "ERROR: repo akim-dotfiles introuvable." >&2
    echo "Attendu: <repo>/${want_path}" >&2
    echo "Solutions:" >&2
    echo "  - cd ~/akim-dotfiles && ~/.config/hypr/scripts/fix-sddm-theme.sh" >&2
    echo "  - ou définir AKIM_DOTFILES_REPO=~/akim-dotfiles" >&2
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
