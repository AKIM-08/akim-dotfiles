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
        cp "$WAL_CACHE/colors-waybar.css" "$HOME/.config/$dir/colors-waybar.css" 2>/dev/null || true
        ln -sf "$WAL_CACHE/colors-waybar.css" "$HOME/.config/$dir/colors-waybar.css" 2>/dev/null || true
    done
    ln -sf "$WAL_CACHE/cpmenu-layout" "$HOME/.config/cpmenu/layout" 2>/dev/null || true
}

apply_gtk_colors() {
    local gtk_css="$WAL_CACHE/colors-gtk.css"
    [ -f "$gtk_css" ] || return 0
    mkdir -p "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"
    
    # GTK3 Styling (Blueman, Pavucontrol, File Choosers, etc.)
    cat "$gtk_css" > "$HOME/.config/gtk-3.0/gtk.css"
    cat << 'EOF' >> "$HOME/.config/gtk-3.0/gtk.css"

window, .background {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}

view, textview text, treeview.view, list, row {
    background-color: @theme_base_color;
    color: @theme_text_color;
}

headerbar, toolbar, menubar, .titlebar {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
    border-bottom: 1px solid alpha(@theme_fg_color, 0.12);
}

headerbar .title, headerbar .subtitle, headerbar label {
    color: @theme_fg_color;
}

button {
    background-color: alpha(@theme_fg_color, 0.08);
    color: @theme_fg_color;
    border: 1px solid alpha(@theme_fg_color, 0.12);
    border-radius: 8px;
    padding: 6px 12px;
}

button:hover {
    background-color: alpha(@theme_selected_bg_color, 0.25);
    border-color: @theme_selected_bg_color;
    color: @theme_fg_color;
}

button:active, button:checked {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

button.suggested-action {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
    border: 1px solid @theme_selected_bg_color;
}

filechooser, filechooserdialog, .filechooser, dialog {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}

.path-bar button, pathbar button {
    background-color: alpha(@theme_fg_color, 0.08);
    color: @theme_fg_color;
    border: 1px solid alpha(@theme_fg_color, 0.12);
    border-radius: 6px;
    margin: 2px;
}

.path-bar button:hover, pathbar button:hover {
    background-color: alpha(@theme_fg_color, 0.18);
    color: @theme_fg_color;
}

.path-bar button:checked, pathbar button:checked {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

.path-bar button label, pathbar button label {
    color: @theme_fg_color;
}

entry, searchbar entry {
    background-color: alpha(@theme_fg_color, 0.06);
    color: @theme_fg_color;
    border: 1px solid alpha(@theme_fg_color, 0.18);
    border-radius: 6px;
    padding: 6px 10px;
    caret-color: @theme_fg_color;
}

entry:focus, searchbar entry:focus {
    border-color: @theme_selected_bg_color;
    background-color: alpha(@theme_fg_color, 0.10);
    color: @theme_fg_color;
}

entry selection {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

placessidebar, placesview, .sidebar {
    background-color: @theme_base_color;
    color: @theme_text_color;
    border-right: 1px solid alpha(@theme_fg_color, 0.08);
}

placessidebar row:hover, placesview row:hover {
    background-color: alpha(@theme_fg_color, 0.08);
    color: @theme_fg_color;
}

placessidebar row:selected, placesview row:selected {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

switch:checked {
    background-color: @theme_selected_bg_color;
    border-color: @theme_selected_bg_color;
}

selection, *:selected, row:selected, treeview.view:selected {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

scrollbar slider {
    background-color: alpha(@theme_fg_color, 0.2);
    border-radius: 6px;
}
EOF

    # GTK4 et Libadwaita (Nautilus)
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
    if command -v gsettings &>/dev/null; then
        [ -n "$gtk_theme" ] && gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" 2>/dev/null || true
        gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark' 2>/dev/null || true
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
    if pgrep -x Hyprland >/dev/null 2>&1; then
        hyprctl reload 2>/dev/null || true
    fi
    if pgrep -x waybar >/dev/null 2>&1; then
        pkill -SIGUSR2 waybar 2>/dev/null || true
    fi
    if pgrep -x swaync >/dev/null 2>&1 && command -v swaync-client &>/dev/null; then
        timeout 2 swaync-client --reload-css 2>/dev/null || true
    fi
    if pgrep -x kitty >/dev/null 2>&1; then
        pkill -SIGUSR1 kitty 2>/dev/null || true
        command -v kitty &>/dev/null && kitty @ set-colors --all --configured "$WAL_CACHE/colors-kitty.conf" 2>/dev/null || true
    fi
}

if [ ! -f "$WALLPAPER" ]; then
    notify-send "Theme" "Wallpaper not found: $WALLPAPER" -u critical 2>/dev/null || true
    exit 1
fi

mkdir -p "$WAL_CACHE"

# Extraction des couleurs directement depuis l'image de fond d'écran active
if wal -i "$WALLPAPER" -n -q --cols16 2>/dev/null; then
    :
elif wal -i "$WALLPAPER" -n --cols16 2>/dev/null; then
    :
else
    echo "WARNING: pywal16 failed, extracting palette via fallback..." >&2
    python3 "$SCRIPT_DIR/pywal-fallback.py" "$WALLPAPER" || exit 1
fi

# Dupliquer colors-hyprland.conf vers colors-hyprland.hl pour Hyprland 0.57+
if [ -f "$WAL_CACHE/colors-hyprland.conf" ]; then
    cp "$WAL_CACHE/colors-hyprland.conf" "$WAL_CACHE/colors-hyprland.hl"
fi

link_pywal_css
apply_gtk_colors
apply_qt_colors
command -v pywal-discord &>/dev/null && pywal-discord -t default

# Recolorer les dossiers Papirus silencieusement sans bloquer
timeout 3 python3 "$SCRIPT_DIR/apply-papirus-color.py" 2>/dev/null || true

reload_ui
echo "--> Theme applied successfully."
