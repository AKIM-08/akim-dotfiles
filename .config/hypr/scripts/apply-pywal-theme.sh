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

/* Global Window and Background */
window, .background, dialog, window.dialog, messagedialog, window.messagedialog {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
}

view, textview text, treeview.view, list, row, scrolledwindow, viewport {
    background-color: @theme_base_color !important;
    color: @theme_text_color !important;
}

/* Headerbars, Toolbars, and Menubars */
headerbar,
headerbar.titlebar,
toolbar,
menubar,
.titlebar,
headerbar:backdrop,
headerbar.default-decoration,
.dialog-action-box,
.dialog-action-area {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border-bottom: 1px solid alpha(@theme_fg_color, 0.12) !important;
}

headerbar .title,
headerbar .subtitle,
headerbar label,
headerbar stack label,
.titlebar label {
    color: @theme_fg_color !important;
    text-shadow: none !important;
}

/* Universal Buttons (Headerbar, Dialog, Pathbar, Regular) */
button,
headerbar button,
toolbar button,
.titlebar button,
dialog button,
pathbar button,
.path-bar button,
filechooser button,
.dialog-action-area button,
.dialog-action-box button {
    background-color: alpha(@theme_fg_color, 0.08) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.18) !important;
    border-radius: 8px !important;
    padding: 6px 12px;
    box-shadow: none !important;
    text-shadow: none !important;
}

button label,
headerbar button label,
toolbar button label,
dialog button label,
pathbar button label,
.path-bar button label,
filechooser button label {
    color: @theme_fg_color !important;
    text-shadow: none !important;
}

button image,
headerbar button image,
toolbar button image,
pathbar button image,
.path-bar button image {
    color: @theme_fg_color !important;
}

button:hover,
headerbar button:hover,
toolbar button:hover,
dialog button:hover,
pathbar button:hover,
.path-bar button:hover,
filechooser button:hover {
    background-color: alpha(@theme_selected_bg_color, 0.25) !important;
    background-image: none !important;
    border-color: @theme_selected_bg_color !important;
    color: @theme_fg_color !important;
}

button:active,
button:checked,
headerbar button:checked,
pathbar button:checked,
.path-bar button:checked {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
    border-color: @theme_selected_bg_color !important;
}

button.suggested-action,
headerbar button.suggested-action,
dialog button.suggested-action {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
    border: 1px solid @theme_selected_bg_color !important;
}

button.suggested-action:hover,
headerbar button.suggested-action:hover {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
}

button.destructive-action,
headerbar button.destructive-action {
    background-color: #eb6f92 !important;
    background-image: none !important;
    color: #ffffff !important;
}

/* ==========================================================================
   File Chooser & Dialog Specific Styles (No White Areas)
   ========================================================================== */
filechooser,
filechooserdialog,
.filechooser,
dialog,
window.dialog,
window.dialog.filechooser,
dialog.filechooser {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
}

filechooser box,
filechooser .horizontal,
filechooser box.horizontal,
filechooser .vertical,
filechooser box.vertical,
filechooser actionbar,
filechooser actionbar box,
filechooser searchbar,
filechooser searchbar box,
filechooser stack,
filechooser paned,
filechooser scrolledwindow,
filechooser .dialog-vbox,
filechooser .dialog-action-box,
filechooser .dialog-action-area,
actionbar,
actionbar box,
.dialog-vbox,
.dialog-action-box,
.dialog-action-area {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: none !important;
}

/* Path Bar & Breadcrumbs Container */
pathbar,
.path-bar,
filechooser pathbar,
filechooser .path-bar,
filechooser .path-bar-box,
filechooser box.path-bar-box,
box.path-bar-box,
box.linked.path-bar,
box.linked {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    border: none !important;
}

pathbar button,
.path-bar button,
filechooser .path-bar-box button,
filechooser .path-bar button,
box.linked.path-bar button {
    background-color: alpha(@theme_fg_color, 0.08) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.18) !important;
    border-radius: 6px !important;
    margin: 2px;
    box-shadow: none !important;
    text-shadow: none !important;
}

pathbar button:hover,
.path-bar button:hover,
filechooser .path-bar-box button:hover {
    background-color: alpha(@theme_fg_color, 0.22) !important;
    background-image: none !important;
    border-color: @theme_selected_bg_color !important;
    color: @theme_fg_color !important;
}

pathbar button:checked,
.path-bar button:checked,
filechooser .path-bar-box button:checked {
    background-color: @theme_selected_bg_color !important;
    background-image: none !important;
    color: @theme_selected_fg_color !important;
}

/* TreeView Header */
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

/* Text Entries and Search inputs */
entry,
searchbar entry,
filechooser entry,
headerbar entry {
    background-color: alpha(@theme_fg_color, 0.06) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.18) !important;
    border-radius: 6px;
    padding: 6px 10px;
    caret-color: @theme_fg_color;
    box-shadow: none !important;
}

entry:focus,
searchbar entry:focus,
filechooser entry:focus,
headerbar entry:focus {
    border-color: @theme_selected_bg_color !important;
    background-color: alpha(@theme_fg_color, 0.10) !important;
    background-image: none !important;
    color: @theme_fg_color !important;
}

entry selection {
    background-color: @theme_selected_bg_color !important;
    color: @theme_selected_fg_color !important;
}

/* Places Sidebar (Left Navigation) */
placessidebar,
placesview,
.sidebar,
.navigation-sidebar,
filechooser placessidebar,
filechooser placesview {
    background-color: @theme_base_color !important;
    background-image: none !important;
    color: @theme_text_color !important;
    border-right: 1px solid alpha(@theme_fg_color, 0.08) !important;
}

placessidebar row:hover,
placesview row:hover {
    background-color: alpha(@theme_fg_color, 0.08) !important;
    color: @theme_fg_color !important;
}

placessidebar row:selected,
placesview row:selected {
    background-color: @theme_selected_bg_color !important;
    color: @theme_selected_fg_color !important;
}

/* Dropdowns & Comboboxes (Custom Files filter, GParted selector) */
combobox,
combobox button,
combobox.linked button,
combobox cellview,
combobox entry,
combobox box,
filechooser combobox,
filechooser combobox button,
filechooser combobox cellview,
filechooser combobox box,
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
filechooser combobox button:hover,
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
filechooser combobox cellview,
filechooser combobox label,
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

menu, popover, popover.background, popover contents {
    background-color: @theme_bg_color !important;
    background-image: none !important;
    color: @theme_fg_color !important;
    border: 1px solid alpha(@theme_fg_color, 0.15) !important;
    border-radius: 8px;
    padding: 4px;
}

menuitem, modelbutton {
    color: @theme_fg_color !important;
    border-radius: 4px;
    padding: 6px 12px;
}

menuitem:hover, modelbutton:hover {
    background-color: @theme_selected_bg_color !important;
    color: @theme_selected_fg_color !important;
}

/* Checkboxes and Radios ("Open files read-only") */
checkbutton,
checkbutton check,
checkbutton label,
radiobutton,
radiobutton radio,
radiobutton label {
    color: @theme_fg_color !important;
    text-shadow: none !important;
}

checkbutton check,
radiobutton radio {
    background-color: alpha(@theme_fg_color, 0.10) !important;
    border: 1px solid alpha(@theme_fg_color, 0.25) !important;
    border-radius: 4px;
}

checkbutton check:checked,
radiobutton radio:checked {
    background-color: @theme_selected_bg_color !important;
    border-color: @theme_selected_bg_color !important;
    color: @theme_selected_fg_color !important;
}

/* Labels */
label {
    color: @theme_fg_color !important;
}

label.dim-label,
label:disabled {
    color: alpha(@theme_fg_color, 0.5) !important;
}

/* Scrollbars */
scrollbar slider {
    background-color: alpha(@theme_fg_color, 0.2) !important;
    border-radius: 6px;
}

scrollbar slider:hover {
    background-color: alpha(@theme_fg_color, 0.4) !important;
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

    # GTK4 et Libadwaita (Nautilus, etc.)
    cat "$gtk_css" > "$HOME/.config/gtk-4.0/gtk.css"
    cat << 'EOF' >> "$HOME/.config/gtk-4.0/gtk.css"
@define-color window_bg_color @theme_bg_color;
@define-color window_fg_color @theme_fg_color;
@define-color view_bg_color @theme_base_color;
@define-color view_fg_color @theme_text_color;
@define-color headerbar_bg_color @theme_bg_color;
@define-color headerbar_fg_color @theme_fg_color;
@define-color headerbar_border_color alpha(@theme_fg_color, 0.12);
@define-color headerbar_backdrop_color @theme_bg_color;
@define-color headerbar_shade_color @theme_bg_color;
@define-color popover_bg_color @theme_bg_color;
@define-color popover_fg_color @theme_fg_color;
@define-color card_bg_color alpha(@theme_fg_color, 0.08);
@define-color card_fg_color @theme_fg_color;
@define-color dialog_bg_color @theme_bg_color;
@define-color dialog_fg_color @theme_fg_color;
@define-color accent_color @theme_selected_bg_color;
@define-color accent_bg_color @theme_selected_bg_color;
@define-color accent_fg_color @theme_selected_fg_color;

window, .background, dialog, window.dialog {
    background-color: @window_bg_color !important;
    color: @window_fg_color !important;
}

headerbar, .titlebar {
    background-color: @headerbar_bg_color !important;
    color: @headerbar_fg_color !important;
    border-bottom: 1px solid alpha(@window_fg_color, 0.12) !important;
}

headerbar .title, headerbar .subtitle, headerbar label {
    color: @headerbar_fg_color !important;
}

button, headerbar button, dialog button {
    background-color: alpha(@window_fg_color, 0.08) !important;
    color: @window_fg_color !important;
    border: 1px solid alpha(@window_fg_color, 0.18) !important;
    border-radius: 8px !important;
}

button:hover, headerbar button:hover {
    background-color: alpha(@window_fg_color, 0.20) !important;
    border-color: @accent_bg_color !important;
}

button:checked, button:active {
    background-color: @accent_bg_color !important;
    color: @accent_fg_color !important;
}

entry {
    background-color: alpha(@window_fg_color, 0.06) !important;
    color: @window_fg_color !important;
    border: 1px solid alpha(@window_fg_color, 0.18) !important;
    border-radius: 6px !important;
}

.navigation-sidebar, placessidebar {
    background-color: @view_bg_color !important;
    color: @view_fg_color !important;
}
EOF

    local gtk_theme
    gtk_theme=$(grep '^gtk-theme-name=' "$HOME/.config/gtk-3.0/settings.ini" 2>/dev/null | cut -d= -f2)
    if [ -z "$gtk_theme" ] || { [ ! -d "/usr/share/themes/$gtk_theme" ] && [ ! -d "$HOME/.themes/$gtk_theme" ] && [ ! -d "$HOME/.local/share/themes/$gtk_theme" ]; }; then
        gtk_theme="Adwaita-dark"
    fi
    if command -v gsettings &>/dev/null; then
        gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" 2>/dev/null || true
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
