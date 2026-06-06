#!/bin/bash
# apply-pywal-theme.sh - Regenerate UI colors from the active wallpaper via pywal16
# Usage: apply-pywal-theme.sh [path/to/wallpaper.jpg]

set -uo pipefail

WALLPAPER="${1:-$HOME/Pictures/wallpapers/current.jpg}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAL_CACHE="$HOME/.cache/wal"

link_pywal_css() {
    local dir
    for dir in waybar swaync cpmenu; do
        mkdir -p "$HOME/.config/$dir"
        ln -sf "$WAL_CACHE/colors-waybar.css" "$HOME/.config/$dir/colors-waybar.css" 2>/dev/null || true
    done
    ln -sf "$WAL_CACHE/cpmenu-layout" "$HOME/.config/cpmenu/layout" 2>/dev/null || true
}

apply_gtk_colors() {
    local gtk_css="$WAL_CACHE/colors-gtk.css"
    [ -f "$gtk_css" ] || return 0
    mkdir -p "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"
    cp "$gtk_css" "$HOME/.config/gtk-3.0/gtk.css"
    
    # Pour GTK4 et Libadwaita (Nautilus)
    cat "$gtk_css" > "$HOME/.config/gtk-4.0/gtk.css"
    cat << 'EOF' >> "$HOME/.config/gtk-4.0/gtk.css"
@define-color window_bg_color @theme_bg_color;
@define-color window_fg_color @theme_fg_color;
@define-color view_bg_color @theme_base_color;
@define-color view_fg_color @theme_text_color;
@define-color headerbar_bg_color @theme_bg_color;
@define-color headerbar_fg_color @theme_fg_color;
@define-color popover_bg_color @theme_bg_color;
@define-color popover_fg_color @theme_fg_color;
@define-color card_bg_color alpha(@theme_fg_color, 0.08);
@define-color card_fg_color @theme_fg_color;
@define-color dialog_bg_color @theme_bg_color;
@define-color dialog_fg_color @theme_fg_color;
@define-color accent_color @theme_selected_bg_color;
@define-color accent_bg_color @theme_selected_bg_color;
@define-color accent_fg_color @theme_selected_fg_color;
EOF

    local gtk_theme
    gtk_theme=$(grep '^gtk-theme-name=' "$HOME/.config/gtk-3.0/settings.ini" 2>/dev/null | cut -d= -f2)
    if [ -n "$gtk_theme" ] && command -v gsettings &>/dev/null; then
        gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" 2>/dev/null || true
        gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
        gsettings set org.gnome.desktop.interface font-name 'JetBrainsMono Nerd Font 11' 2>/dev/null || true
    fi
}

apply_qt_colors() {
    local qt_conf="$WAL_CACHE/qt-pywal.conf"
    [ -f "$qt_conf" ] || return 0
    mkdir -p "$HOME/.config/qt5ct/colors" "$HOME/.config/qt6ct/colors"
    cp "$qt_conf" "$HOME/.config/qt5ct/colors/pywal.conf" 2>/dev/null || true
    cp "$qt_conf" "$HOME/.config/qt6ct/colors/pywal.conf" 2>/dev/null || true
}

reload_ui() {
    hyprctl reload 2>/dev/null || true
    pkill waybar 2>/dev/null || true
    waybar & disown || true
    if pgrep -x nautilus >/dev/null 2>&1; then
        nautilus -q 2>/dev/null || pkill -x nautilus 2>/dev/null || true
        # Relancer nautilus avec le nouveau thème GTK (délai pour laisser le temps au CSS)
        sleep 1 && nautilus & disown 2>/dev/null || true
    fi
    if command -v swaync-client &>/dev/null; then
        swaync-client --reload-css 2>/dev/null || true
        # Redémarrer complètement swaync pour resynchroniser le widget backlight
        pkill swaync 2>/dev/null || true
        sleep 0.3
        swaync & disown || true
    else
        pkill swaync 2>/dev/null || true
        swaync & disown || true
    fi
}

if [ ! -f "$WALLPAPER" ]; then
    notify-send "Theme" "Wallpaper not found: $WALLPAPER" -u critical 2>/dev/null || true
    exit 1
fi

mkdir -p "$WAL_CACHE"

if wal -i "$WALLPAPER" -n -q --cols16; then
    :
elif wal -i "$WALLPAPER" -n --cols16; then
    :
else
    echo "WARNING: pywal16 failed, extracting palette from image..." >&2
    python3 "$SCRIPT_DIR/pywal-fallback.py" "$WALLPAPER" || exit 1
fi

link_pywal_css
apply_gtk_colors
apply_qt_colors
command -v pywal-discord &>/dev/null && pywal-discord -t default

# Recolorer les dossiers Papirus (si papirus-folders est installé)
python3 "$SCRIPT_DIR/apply-papirus-color.py" 2>/dev/null || true

reload_ui
