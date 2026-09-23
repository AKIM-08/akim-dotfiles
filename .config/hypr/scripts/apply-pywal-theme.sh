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
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border-bottom: 1px solid alpha(@theme_fg_color, 0.12) !important;
}

headerbar .title, headerbar .subtitle, headerbar label {
    color: @theme_fg_color !important;
}

button,
headerbar button,
toolbar button,
.titlebar button {
    background-color: alpha(@theme_fg_color, 0.08) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.16) !important;
    border-radius: 8px !important;
    padding: 6px 12px;
    box-shadow: none !important;
    text-shadow: none !important;
}

button label,
headerbar button label,
toolbar button label {
    color: @theme_fg_color !important;
    text-shadow: none !important;
}

button:hover,
headerbar button:hover,
toolbar button:hover {
    background-color: alpha(@theme_selected_bg_color, 0.25) !important;
    background-image: none !important;
    border-color: @theme_selected_bg_color !important;
    color: @theme_fg_color !important;
}

button:active, button:checked,
headerbar button:checked {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
}

button.suggested-action,
headerbar button.suggested-action {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
    border: 1px solid @theme_selected_bg_color !important;
}

filechooser, filechooserdialog, .filechooser, dialog, window.dialog {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
}

filechooser box,
filechooser .horizontal,
filechooser box.horizontal,
filechooser actionbar,
filechooser actionbar box,
filechooser searchbar,
actionbar,
actionbar box {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: none !important;
}

pathbar,
.path-bar,
filechooser pathbar,
filechooser .path-bar {
    background-color: @theme_bg_color !important;
    background-image: none !important;
}

.path-bar button, pathbar button,
.path-bar button label, pathbar button label,
.path-bar button image, pathbar button image {
    background-color: alpha(@theme_fg_color, 0.08) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.16) !important;
    border-radius: 6px !important;
    margin: 2px;
    box-shadow: none !important;
    text-shadow: none !important;
}

.path-bar button:hover, pathbar button:hover {
    background-color: alpha(@theme_fg_color, 0.20) !important;
    background-image: none !important;
    border-color: @theme_selected_bg_color !important;
    color: @theme_fg_color !important;
}

.path-bar button:checked, pathbar button:checked {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
}

treeview.view header,
treeview.view header button,
treeview.view header button box,
treeview.view header button label,
treeview.view header button image,
treeview header,
treeview header button {
    background-color: @theme_base_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: none !important;
    border-bottom: 1px solid alpha(@theme_fg_color, 0.15) !important;
    box-shadow: none !important;
    text-shadow: none !important;
}

treeview.view header button:hover {
    background-color: alpha(@theme_selected_bg_color, 0.25) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
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

/* Dropdowns & Comboboxes (GParted device selector, etc.) */
combobox,
combobox button,
combobox.linked button,
combobox cellview,
combobox entry,
combobox box,
toolbar combobox,
toolbar combobox button,
toolbar combobox cellview,
toolbar .combo,
.combo,
.combobox-entry {
    background-color: alpha(@theme_fg_color, 0.08) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.22) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    text-shadow: none !important;
}

combobox:hover,
combobox button:hover,
toolbar combobox button:hover,
toolbar combobox:hover {
    background-color: alpha(@theme_fg_color, 0.16) !important;
    background-image: none !important;
    border-color: @theme_selected_bg_color !important;
    color: @theme_fg_color !important;
}

combobox cellview,
combobox cellview label,
combobox label,
combobox text,
combobox entry,
combobox arrow,
toolbar combobox cellview,
toolbar combobox label {
    color: @theme_fg_color !important;
    background-color: transparent !important;
    background-image: none !important;
    text-shadow: none !important;
}

combobox window,
combobox menu,
combobox popover {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
}

/* Swappy Screenshot Annotation Editor */
window.swappy, .swappy, #swappy {
    background-color: @theme_bg_color;
    color: @theme_fg_color;
}

window.swappy headerbar,
window.swappy toolbar,
window.swappy .toolbar,
window.swappy box.horizontal {
    background-color: alpha(@theme_fg_color, 0.08);
    color: @theme_fg_color;
    border-bottom: 2px solid alpha(@theme_fg_color, 0.15);
    padding: 6px 10px;
}

window.swappy button {
    background-color: alpha(@theme_fg_color, 0.12);
    color: @theme_fg_color;
    border: 1px solid alpha(@theme_fg_color, 0.25);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 2px 4px;
    min-height: 32px;
    min-width: 32px;
}

window.swappy button image {
    color: @theme_fg_color;
    -gtk-icon-style: regular;
}

window.swappy button:hover {
    background-color: alpha(@theme_selected_bg_color, 0.35);
    border-color: @theme_selected_bg_color;
    color: @theme_fg_color;
}

window.swappy button:active,
window.swappy button:checked {
    background-color: @theme_selected_bg_color;
    border-color: @theme_selected_fg_color;
    color: @theme_selected_fg_color;
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
