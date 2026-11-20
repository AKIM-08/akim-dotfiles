#!/bin/bash
# apply-pywal-theme.sh - Apply UI colors generated from a wallpaper via pywal16
# Usage:
#   apply-pywal-theme.sh [path/to/wallpaper.jpg]   apply the theme for one wallpaper
#   apply-pywal-theme.sh --precache                build missing palettes for every wallpaper
#
# Palettes are generated once per wallpaper and cached in ~/.cache/wal/palettes/<key>/.
# Switching to an already-cached wallpaper only copies files and recolors live apps
# in place (no Hyprland reload, no Waybar restart).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
WAL_CACHE="$HOME/.cache/wal"
PALETTE_ROOT="$WAL_CACHE/palettes"
WALLPAPER_DIR="$HOME/Pictures/wallpapers"
# Bump to invalidate every cached palette after changing how palettes are built.
CACHE_VERSION=8

# Cache key: wallpaper identity + anything that changes the generated files
# (pywal templates, the fallback extractor and this script's GTK CSS).
palette_key() {
    local real stamp
    real=$(readlink -f "$1") || return 1
    stamp=$(find "$HOME/.config/wal/templates" "$SCRIPT_DIR/pywal-fallback.py" "$SCRIPT_PATH" \
        -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
    printf '%s|%s|%s|%s' "$CACHE_VERSION" "$real" "$(stat -Lc '%s %Y' "$real")" "$stamp" \
        | md5sum | cut -c1-16
}

# Generate a palette into $2 without touching the live ~/.cache/wal.
build_palette() {
    local wallpaper="$1" out="$2" tmp src
    tmp=$(mktemp -d) || return 1
    src="$tmp/wal"

    # -s/-t: no terminal escape sequences, -e: no gtk/xrdb reloads. We recolor apps ourselves.
    if ! XDG_CACHE_HOME="$tmp" PYWAL_CACHE_DIR="$src" wal -i "$wallpaper" -n -s -t -e -q --cols16 >/dev/null 2>&1 \
        || [ ! -f "$src/colors.json" ]; then
        echo "WARNING: pywal16 failed, extracting palette via fallback..." >&2
        rm -rf "$src"
        if ! PYWAL_CACHE_DIR="$src" python3 "$SCRIPT_DIR/pywal-fallback.py" "$wallpaper"; then
            rm -rf "$tmp"
            return 1
        fi
    fi

    # Hyprland 0.57+ reads colors-hyprland.hl
    [ -f "$src/colors-hyprland.conf" ] && cp "$src/colors-hyprland.conf" "$src/colors-hyprland.hl"
    write_rofi_colors "$src" || echo "WARNING: could not write Rofi colors" >&2
    write_cava_config "$src" || echo "WARNING: could not write the Cava config" >&2
    write_sequences "$src" || echo "WARNING: could not write the terminal color sequences" >&2
    write_btop_theme "$src" || echo "WARNING: could not write the btop theme" >&2
    write_fastfetch_logo "$wallpaper" "$src" || echo "WARNING: could not write the fastfetch logo" >&2
    build_gtk_css "$src"
    rm -rf "$src/schemes"

    # Publish atomically so a concurrent reader never sees a half-built palette.
    mkdir -p "$PALETTE_ROOT"
    if ! mv -T "$src" "$out" 2>/dev/null; then
        [ -f "$out/colors.json" ] || { rm -rf "$tmp"; return 1; }   # lost a race, other copy is fine
    fi
    rm -rf "$tmp"
}

# Rofi colors, imported by every ~/.config/rofi/*.rasi as "~/.cache/wal/colors-rofi-dark".
# Generated from colors.json rather than a pywal template: pywal formats templates with
# Python str.format, which breaks on the literal braces of a rasi block.
# Accent is color1, the same as the Waybar active workspace.
write_rofi_colors() {
    python3 -I - "$1" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
data = json.loads((d / "colors.json").read_text())
s, c = data["special"], data["colors"]

def blend(a, b, t):
    """Mix hex colors a and b (t = share of b)."""
    pa, pb = (tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))

# Menus: background lifted 12% toward the text color, 65% opaque (frosted, not black)
menu_bg = blend(s["background"], s["foreground"], 0.12) + "a6"
(d / "colors-rofi-dark").write_text(f"""* {{
    background-color: {s['background']};
    text-color:       {s['foreground']};
    border-color:     {c['color1']};
    selected-normal-background: {c['color1']};
    selected-normal-foreground: {s['background']};
    active-background: {c['color2']};
    active-foreground: {s['background']};
    urgent-background: {c['color9']};
    urgent-foreground: {s['background']};
    background-translucent: {s['background']}d9;
    accent-translucent: {c['color1']}99;
    accent-soft: {c['color1']}2e;
    menu-background: {menu_bg};
}}
""")
PY
}

# Cava config (~/.config/cava/config links to ~/.cache/wal/colors-cava): the bars are a
# gradient of the wallpaper's accent, dark at the bottom, light at the top. Running cava
# instances recolor on SIGUSR2 (see reload_ui).
write_cava_config() {
    python3 -I - "$1" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
data = json.loads((d / "colors.json").read_text())
s, c = data["special"], data["colors"]

def blend(a, b, t):
    pa, pb = (tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))

accent, bright = c["color1"], c.get("color9") or c["color1"]
stops = [blend(accent, s["background"], 0.35), accent, bright, blend(bright, s["foreground"], 0.55)]
colors = "\n".join(f"gradient_color_{i} = '{v}'" for i, v in enumerate(stops, 1))
(d / "colors-cava").write_text(f"""## Generated by ~/.config/hypr/scripts/apply-pywal-theme.sh from the wallpaper's colors.
## Changes here are replaced on the next wallpaper switch.

[general]
framerate = 60
bar_width = 2
bar_spacing = 1

[output]
method = noncurses

[color]
# Bars: the wallpaper's accent, darker at the bottom, lighter at the top
gradient = 1
gradient_count = {len(stops)}
{colors}

[smoothing]
monstercat = 1
noise_reduction = 77
""")
PY
}

# fastfetch logo (~/.cache/wal/fastfetch-logo.png): the whole wallpaper (16:9) cut into five
# vertical strips with small transparent gaps and rounded ends. fastfetch's config shows it 34x9
# text cells, which keeps the 16:9 shape in kitty. Needs Pillow (python3-pil).
write_fastfetch_logo() {
    python3 -I - "$1" "$2" <<'PY'
import pathlib, sys
try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError:
    sys.exit(0)
wall, d = sys.argv[1], pathlib.Path(sys.argv[2])
W, H, N, K = 720, 405, 5, 4                  # size, strips, oversampling for smooth corners
gap = round(W * 0.035)
strip = (W - (N - 1) * gap) / N
img = ImageOps.fit(Image.open(wall).convert("RGB"), (W, H), Image.LANCZOS).convert("RGBA")
mask = Image.new("L", (W * K, H * K), 0)
draw = ImageDraw.Draw(mask)
for i in range(N):
    x = i * (strip + gap)
    draw.rounded_rectangle((round(x * K), 0, round((x + strip) * K) - 1, H * K - 1), radius=14 * K, fill=255)
img.putalpha(mask.resize((W, H), Image.LANCZOS))
img.save(d / "fastfetch-logo.png")
PY
}

# btop theme (~/.config/btop/themes/pywal.theme links to ~/.cache/wal/btop-pywal.theme):
# graphs fade from the wallpaper's cool colors to its accent, boxes are a soft accent line, no
# background (btop.conf: theme_background = false) so kitty's blur shows through.
write_btop_theme() {
    python3 -I - "$1" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
data = json.loads((d / "colors.json").read_text())
s, c = data["special"], data["colors"]
bg, fg = s["background"], s["foreground"]

def blend(a, b, t):
    pa, pb = (tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for h in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))

line = blend(c["color1"], bg, 0.45)
t = {
    "main_bg": bg, "main_fg": c["color7"], "title": c["color15"], "hi_fg": c["color1"],
    "selected_bg": blend(c["color1"], bg, 0.65), "selected_fg": c["color15"],
    "inactive_fg": c["color8"], "graph_text": c["color7"], "meter_bg": blend(c["color8"], bg, 0.5),
    "proc_misc": c["color6"], "cpu_box": line, "mem_box": line, "net_box": line, "proc_box": line,
    "div_line": blend(c["color8"], bg, 0.4),
    "temp_start": c["color6"], "temp_mid": c["color3"], "temp_end": c["color1"],
    "cpu_start": c["color2"], "cpu_mid": c["color6"], "cpu_end": c["color1"],
    "free_start": c["color2"], "free_mid": c["color6"], "free_end": c["color4"],
    "cached_start": c["color4"], "cached_mid": c["color5"], "cached_end": c["color13"] if "color13" in c else c["color5"],
    "available_start": c["color6"], "available_mid": c["color4"], "available_end": c["color12"] if "color12" in c else c["color4"],
    "used_start": c["color5"], "used_mid": c["color3"], "used_end": c["color1"],
    "download_start": c["color6"], "download_mid": c["color4"], "download_end": c["color5"],
    "upload_start": c["color3"], "upload_mid": c["color9"] if "color9" in c else c["color1"], "upload_end": c["color1"],
    "process_start": c["color2"], "process_mid": c["color3"], "process_end": c["color1"],
}
lines = ["# Generated by ~/.config/hypr/scripts/apply-pywal-theme.sh from the wallpaper's colors"]
lines += [f'theme[{k}]="{v}"' for k, v in t.items()]
(d / "btop-pywal.theme").write_text("\n".join(lines) + "\n")
PY
}

# Terminal color escape codes (~/.cache/wal/sequences), pushed into every open terminal by
# reload_ui so they recolor in place. Written here from colors.json: palettes are built with
# `wal -s`, which writes no sequences file, and an old one left in the cache would repaint
# every open terminal with a previous wallpaper's colors.
write_sequences() {
    python3 -I - "$1" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
data = json.loads((d / "colors.json").read_text())
s, c = data["special"], data["colors"]
ST = "\033\\"
out = "".join(f"\033]4;{i};{c[f'color{i}']}{ST}" for i in range(16) if f"color{i}" in c)
out += f"\033]10;{s['foreground']}{ST}\033]11;{s['background']}{ST}\033]12;{c['color1']}{ST}"   # cursor in the accent
(d / "sequences").write_text(out)
PY
}

# Replace a file atomically (readers never see it half-written).
install_file() {
    cp -f "$1" "$2.tmp.$$" && mv -f "$2.tmp.$$" "$2"
}

# Rewrite a file in place. Used for files watched by apps (Waybar's reload_style_on_change),
# so the watcher sees a normal modification of the file it already watches.
write_in_place() {
    [ -L "$2" ] && rm -f "$2"   # migrate old symlinks into ~/.cache/wal
    cat "$1" > "$2"
}

# Waybar's reload_style_on_change reacts to the imported colors file unreliably (it ends up
# showing the previous palette). Rewriting style.css itself, after the new colors are fully
# on disk, makes Waybar re-read both files at the right moment. CSS-only, no restart/blink.
poke_waybar_style() {
    local style="$HOME/.config/waybar/style.css" tmp
    [ -f "$style" ] || return 0
    tmp=$(mktemp) || return 0
    cat "$style" > "$tmp" && cat "$tmp" > "$style"
    rm -f "$tmp"
}

# GTK3 only reads ~/.config/gtk-3.0/gtk.css when an app starts, but it does reload live when
# the theme *name* changes. So the palette goes into one of two generated themes, Pywal-A and
# Pywal-B: write the one not in use, then switch to it. Open GTK3 apps (Blueman, ...) recolor
# immediately. The user gtk.css is reduced to a stub so its old colors can't override the theme.
apply_gtk3_theme() {
    local pal="$1" cur slot dir
    [ -f "$pal/gtk3.css" ] || return 0
    if ! command -v gsettings >/dev/null 2>&1; then
        cat "$pal/gtk3.css" > "$HOME/.config/gtk-3.0/gtk.css"   # no live switching possible
        return 0
    fi

    cur=$(gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null | tr -d "'")
    if [ "$cur" = "Pywal-A" ]; then slot="Pywal-B"; else slot="Pywal-A"; fi
    dir="$HOME/.local/share/themes/$slot"
    mkdir -p "$dir/gtk-3.0"
    printf '[Desktop Entry]\nType=X-GNOME-Metatheme\nName=%s\nComment=Generated by apply-pywal-theme.sh\n\n[X-GNOME-Metatheme]\nGtkTheme=%s\n' \
        "$slot" "$slot" > "$dir/index.theme"
    {
        echo '/* Generated by apply-pywal-theme.sh: Adwaita dark + pywal palette. Do not edit. */'
        echo '@import url("resource:///org/gtk/libgtk/theme/Adwaita/gtk-contained-dark.css");'
        cat "$pal/gtk3.css"
    } > "$dir/gtk-3.0/gtk.css"

    local stub='/* GTK3 colors live in the Pywal-A / Pywal-B themes (see apply-pywal-theme.sh). */'
    [ "$(head -1 "$HOME/.config/gtk-3.0/gtk.css" 2>/dev/null)" = "$stub" ] \
        || echo "$stub" > "$HOME/.config/gtk-3.0/gtk.css"

    gsettings set org.gnome.desktop.interface gtk-theme "$slot" 2>/dev/null
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null
    sed -i "s/^gtk-theme-name=.*/gtk-theme-name=$slot/" "$HOME/.config/gtk-3.0/settings.ini" 2>/dev/null
}

apply_palette() {
    local pal="$1" f dir
    mkdir -p "$WAL_CACHE"
    for f in "$pal"/*; do
        [ -f "$f" ] || continue
        case "$(basename "$f")" in gtk3.css|gtk4.css) continue ;; esac
        install_file "$f" "$WAL_CACHE/$(basename "$f")"
    done

    for dir in waybar swaync cpmenu; do
        mkdir -p "$HOME/.config/$dir"
        write_in_place "$pal/colors-waybar.css" "$HOME/.config/$dir/colors-waybar.css" 2>/dev/null || true
    done
    ln -sf "$WAL_CACHE/cpmenu-layout" "$HOME/.config/cpmenu/layout" 2>/dev/null || true
    mkdir -p "$HOME/.config/btop/themes"
    ln -sf "$WAL_CACHE/btop-pywal.theme" "$HOME/.config/btop/themes/pywal.theme" 2>/dev/null || true
    poke_waybar_style

    mkdir -p "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"
    apply_gtk3_theme "$pal"
    # GTK4/libadwaita only reads this at startup; open GTK4 apps update on their next launch.
    [ -f "$pal/gtk4.css" ] && cat "$pal/gtk4.css" > "$HOME/.config/gtk-4.0/gtk.css"

    if [ -f "$pal/qt-pywal.conf" ]; then
        mkdir -p "$HOME/.config/qt5ct/colors" "$HOME/.config/qt6ct/colors"
        cp "$pal/qt-pywal.conf" "$HOME/.config/qt5ct/colors/pywal.conf" 2>/dev/null || true
        cp "$pal/qt-pywal.conf" "$HOME/.config/qt6ct/colors/pywal.conf" 2>/dev/null || true
    fi
}

# Build the full GTK3/GTK4 stylesheets for a palette into $1/gtk3.css and $1/gtk4.css.
build_gtk_css() {
    local out="$1"
    local gtk_css="$out/colors-gtk.css"
    [ -f "$gtk_css" ] || return 0

    # GTK3 Styling (Blueman, Pavucontrol, File Choosers, etc.)
    cat "$gtk_css" > "$out/gtk3.css"
    cat << 'EOF' >> "$out/gtk3.css"

/* Global Window and Background */
window, .background, dialog, window.dialog, messagedialog, window.messagedialog {
    background-color: @theme_bg_color;
    background-image: none;
    color: @theme_fg_color;
}

view, textview text, treeview.view, list, row, scrolledwindow, viewport {
    background-color: @theme_base_color;
    color: @theme_text_color;
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
    background-color: @theme_bg_color;
    background-image: none;
    color: @theme_fg_color;
    border-bottom: 1px solid @borders;
}

headerbar .title,
headerbar .subtitle,
headerbar label,
headerbar stack label,
.titlebar label {
    color: @theme_fg_color;
    text-shadow: none;
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
    background-color: @theme_base_color;
    background-image: none;
    color: @theme_fg_color;
    border: 1px solid @borders;
    border-radius: 8px;
    padding: 6px 12px;
    box-shadow: none;
    text-shadow: none;
}

button label,
headerbar button label,
toolbar button label,
dialog button label,
pathbar button label,
.path-bar button label,
filechooser button label {
    color: @theme_fg_color;
    text-shadow: none;
}

button image,
headerbar button image,
toolbar button image,
pathbar button image,
.path-bar button image {
    color: @theme_fg_color;
}

button:hover,
headerbar button:hover,
toolbar button:hover,
dialog button:hover,
pathbar button:hover,
.path-bar button:hover,
filechooser button:hover {
    background-color: @theme_selected_bg_color;
    background-image: none;
    border-color: @theme_selected_bg_color;
    color: @theme_fg_color;
}

button:active,
button:checked,
headerbar button:checked,
pathbar button:checked,
.path-bar button:checked {
    background-color: @theme_selected_bg_color;
    background-image: none;
    color: @theme_selected_fg_color;
    border-color: @theme_selected_bg_color;
}

button.suggested-action,
headerbar button.suggested-action,
dialog button.suggested-action {
    background-color: @theme_selected_bg_color;
    background-image: none;
    color: @theme_selected_fg_color;
    border: 1px solid @theme_selected_bg_color;
}

button.suggested-action:hover,
headerbar button.suggested-action:hover {
    background-color: @theme_selected_bg_color;
    background-image: none;
    color: @theme_selected_fg_color;
}

button.destructive-action,
headerbar button.destructive-action {
    background-color: #eb6f92;
    background-image: none;
    color: #ffffff;
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
    background-color: @theme_bg_color;
    background-image: none;
    color: @theme_fg_color;
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
    background-color: @theme_bg_color;
    background-image: none;
    color: @theme_fg_color;
    border: none;
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
    background-color: @theme_bg_color;
    background-image: none;
    border: none;
}

pathbar button,
.path-bar button,
filechooser .path-bar-box button,
filechooser .path-bar button,
box.linked.path-bar button {
    background-color: @theme_base_color;
    background-image: none;
    color: @theme_fg_color;
    border: 1px solid @borders;
    border-radius: 6px;
    margin: 2px;
    box-shadow: none;
    text-shadow: none;
}

pathbar button:hover,
.path-bar button:hover,
filechooser .path-bar-box button:hover {
    background-color: @borders;
    background-image: none;
    border-color: @theme_selected_bg_color;
    color: @theme_fg_color;
}

pathbar button:checked,
.path-bar button:checked,
filechooser .path-bar-box button:checked {
    background-color: @theme_selected_bg_color;
    background-image: none;
    color: @theme_selected_fg_color;
}

/* TreeView Header */
treeview.view header,
treeview.view header button,
treeview.view header button box,
treeview.view header button label,
treeview.view header button image,
treeview header,
treeview header button {
    background-color: @theme_base_color;
    background-image: none;
    color: @theme_fg_color;
    border: none;
    border-bottom: 1px solid @borders;
    box-shadow: none;
    text-shadow: none;
}

treeview.view header button:hover {
    background-color: @theme_selected_bg_color;
    background-image: none;
    color: @theme_fg_color;
}

/* Text Entries and Search inputs */
entry,
searchbar entry,
filechooser entry,
headerbar entry {
    background-color: @theme_base_color;
    background-image: none;
    color: @theme_fg_color;
    border: 1px solid @borders;
    border-radius: 6px;
    padding: 6px 10px;
    caret-color: @theme_fg_color;
    box-shadow: none;
}

entry:focus,
searchbar entry:focus,
filechooser entry:focus,
headerbar entry:focus {
    border-color: @theme_selected_bg_color;
    background-color: @borders;
    background-image: none;
    color: @theme_fg_color;
}

entry selection {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

/* Places Sidebar (Left Navigation) */
placessidebar,
placesview,
.sidebar,
.navigation-sidebar,
filechooser placessidebar,
filechooser placesview {
    background-color: @theme_base_color;
    background-image: none;
    color: @theme_text_color;
    border-right: 1px solid @borders;
}

placessidebar row:hover,
placesview row:hover {
    background-color: @theme_base_color;
    color: @theme_fg_color;
}

placessidebar row:selected,
placesview row:selected {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
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
    background-color: @theme_base_color;
    background-image: none;
    color: @theme_fg_color;
    border: 1px solid @borders;
    border-radius: 8px;
    box-shadow: none;
    text-shadow: none;
}

combobox:hover,
combobox button:hover,
filechooser combobox button:hover,
toolbar combobox button:hover,
toolbar combobox:hover {
    background-color: @borders;
    background-image: none;
    border-color: @theme_selected_bg_color;
    color: @theme_fg_color;
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
    color: @theme_fg_color;
    background-color: transparent;
    background-image: none;
    text-shadow: none;
}

combobox window,
combobox menu,
combobox popover {
    background-color: @theme_bg_color;
    background-image: none;
    color: @theme_fg_color;
}

menu, popover, popover.background, popover contents {
    background-color: @theme_bg_color;
    background-image: none;
    color: @theme_fg_color;
    border: 1px solid @borders;
    border-radius: 8px;
    padding: 4px;
}

menuitem, modelbutton {
    color: @theme_fg_color;
    border-radius: 4px;
    padding: 6px 12px;
}

menuitem:hover, modelbutton:hover {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

/* Checkboxes and Radios ("Open files read-only") */
checkbutton,
checkbutton check,
checkbutton label,
radiobutton,
radiobutton radio,
radiobutton label {
    color: @theme_fg_color;
    text-shadow: none;
}

checkbutton check,
radiobutton radio {
    background-color: @borders;
    border: 1px solid @borders;
    border-radius: 4px;
}

checkbutton check:checked,
radiobutton radio:checked {
    background-color: @theme_selected_bg_color;
    border-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

/* Labels */
label {
    color: @theme_fg_color;
}

label.dim-label,
label:disabled {
    color: @insensitive_fg_color;
}

/* Scrollbars */
scrollbar slider {
    background-color: @borders;
    border-radius: 6px;
}

scrollbar slider:hover {
    background-color: @borders;
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
    background-color: @theme_base_color;
    color: @theme_fg_color;
    border-bottom: 2px solid @borders;
    padding: 6px 10px;
}

window.swappy button {
    background-color: @borders;
    color: @theme_fg_color;
    border: 1px solid @borders;
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
    background-color: @theme_selected_bg_color;
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
    cat "$gtk_css" > "$out/gtk4.css"
    cat << 'EOF' >> "$out/gtk4.css"
@define-color window_bg_color @theme_bg_color;
@define-color window_fg_color @theme_fg_color;
@define-color view_bg_color @theme_base_color;
@define-color view_fg_color @theme_text_color;
@define-color headerbar_bg_color @theme_bg_color;
@define-color headerbar_fg_color @theme_fg_color;
@define-color headerbar_border_color @borders;
@define-color headerbar_backdrop_color @theme_bg_color;
@define-color headerbar_shade_color @theme_bg_color;
@define-color popover_bg_color @theme_bg_color;
@define-color popover_fg_color @theme_fg_color;
@define-color card_bg_color @theme_base_color;
@define-color card_fg_color @theme_fg_color;
@define-color dialog_bg_color @theme_bg_color;
@define-color dialog_fg_color @theme_fg_color;
@define-color accent_color @theme_selected_bg_color;
@define-color accent_bg_color @theme_selected_bg_color;
@define-color accent_fg_color @theme_selected_fg_color;

window, .background, dialog, window.dialog {
    background-color: @window_bg_color;
    color: @window_fg_color;
}

headerbar, .titlebar {
    background-color: @headerbar_bg_color;
    color: @headerbar_fg_color;
    border-bottom: 1px solid @borders;
}

headerbar .title, headerbar .subtitle, headerbar label {
    color: @headerbar_fg_color;
}

button, headerbar button, dialog button {
    background-color: @view_bg_color;
    color: @window_fg_color;
    border: 1px solid @borders;
    border-radius: 8px;
}

button:hover, headerbar button:hover {
    background-color: @borders;
    border-color: @accent_bg_color;
}

button:checked, button:active {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
}

entry {
    background-color: @view_bg_color;
    color: @window_fg_color;
    border: 1px solid @borders;
    border-radius: 6px;
}

.navigation-sidebar, placessidebar {
    background-color: @view_bg_color;
    color: @view_fg_color;
}
EOF

}

# Set Hyprland's active border from the current palette. hyprland.hl deliberately does not
# source the colors file (Hyprland auto-reloads when a sourced file changes); instead it runs
# this via `exec = ... --border` at startup and after each reload.
apply_hypr_border() {
    local conf="$WAL_CACHE/colors-hyprland.conf" border out
    [ -f "$conf" ] || return 0
    border=$(awk '
        $2 == "=" { v[$1] = $3 }
        END { printf "%s %s %s %s %s %s 45deg", v["$color1"], v["$color3"], v["$color5"], v["$color7"], v["$color9"], v["$color11"] }
    ' "$conf" 2>/dev/null)
    out=$(hyprctl keyword general:col.active_border "$border" 2>&1)
    if [ "$out" != "ok" ]; then
        echo "WARNING: hyprctl keyword failed: $out" >&2
        return 1
    fi
}

# Recolor running apps in place. Nothing here restarts or re-parses a whole config.
reload_ui() {
    # Hyprland: only the active border uses pywal colors, so set it directly instead of
    # `hyprctl reload` (which re-applies monitors, animations and rules and visibly flickers).
    # The sourced colors file is already updated, so the next real reload stays consistent.
    if pgrep -x Hyprland >/dev/null 2>&1; then
        apply_hypr_border
    fi

    # Waybar: every theme sets "reload_style_on_change": true, so it restyles itself when
    # colors-waybar.css changes. No SIGUSR2 (that restarts the bar and makes it blink).

    if pgrep -x swaync >/dev/null 2>&1 && command -v swaync-client &>/dev/null; then
        timeout 2 swaync-client --reload-css >/dev/null 2>&1 || true
    fi

    # btop: SIGUSR2 makes it reload its config and theme (the theme file now has the new palette)
    if pgrep -x btop >/dev/null 2>&1; then
        pkill -USR2 -x btop 2>/dev/null || true
    fi

    # Cava: SIGUSR2 re-reads the colors from its config (now the new palette)
    if pgrep -x cava >/dev/null 2>&1; then
        pkill -USR2 -x cava 2>/dev/null || true
    fi

    # Kitty re-reads its config (which includes colors-kitty.conf). `kitty @` can't be used
    # from a keybind: there's no listen_on socket, only the in-window tty channel.
    if pgrep -x kitty >/dev/null 2>&1; then
        pkill -SIGUSR1 -x kitty 2>/dev/null || true
    fi

    # Push the palette into every open terminal (what pywal itself does without -s), so
    # programs already running in them (nmtui, btop, ...) recolor without restarting.
    if [ -f "$WAL_CACHE/sequences" ]; then
        local t
        for t in /dev/pts/[0-9]*; do
            [ -O "$t" ] && [ -w "$t" ] || continue
            timeout 1 sh -c 'cat "$1" > "$2"' _ "$WAL_CACHE/sequences" "$t" 2>/dev/null 8>&- &
        done
    fi
}

# Slow or cosmetic steps that nobody should wait on. Runs after the UI is recolored.
background_tasks() {
    (
        exec 8>&- 9>&-   # release the apply/precache locks; nothing should wait on this
        # Mouse pointer in the wallpaper's accent (only when that pointer theme is chosen).
        # First, so it changes with the rest; instant when it was built in advance (precache).
        python3 "$SCRIPT_DIR/cursors.py" accent
        command -v pywal-discord &>/dev/null && pywal-discord -t default
        timeout 3 python3 "$SCRIPT_DIR/apply-papirus-color.py"

        # (gtk-theme is switched by apply_gtk3_theme)
        if command -v gsettings &>/dev/null; then
            gsettings set org.gnome.desktop.interface icon-theme 'Papirus-Dark'
            gsettings set org.gnome.desktop.interface font-name 'JetBrainsMono Nerd Font 11'
        fi
    ) >/dev/null 2>&1 &
    disown
}

list_wallpapers() {
    find -L "$WALLPAPER_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) \
        ! -name 'current.jpg' 2>/dev/null | sort
}

# Build palettes for every wallpaper that doesn't have one yet, then drop stale ones.
precache() {
    mkdir -p "$PALETTE_ROOT"
    exec 9>"$PALETTE_ROOT/.precache.lock"
    flock -n 9 || exit 0   # another precache is already running

    local img key keep=" "
    while IFS= read -r img; do
        key=$(palette_key "$img") || continue
        keep+="$key "
        [ -f "$PALETTE_ROOT/$key/colors.json" ] && continue
        echo "--> Caching palette for $(basename "$img")"
        build_palette "$img" "$PALETTE_ROOT/$key" || echo "WARNING: failed to build palette for $img" >&2
    done < <(list_wallpapers)

    # Wallpaper-accent mouse pointers for those palettes (only if that pointer theme is chosen)
    python3 "$SCRIPT_DIR/cursors.py" precache

    # Remove palettes that no longer match a wallpaper here and haven't been used in 30 days
    # (palettes for images picked from elsewhere via Waypaper survive while in use).
    local d
    while IFS= read -r d; do
        [[ "$keep" == *" $(basename "$d") "* ]] || rm -rf "$d"
    done < <(find "$PALETTE_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +30)
}

case "${1:-}" in
    --precache) precache; exit 0 ;;
    --border)   apply_hypr_border; exit $? ;;
esac

WALLPAPER="${1:-$WALLPAPER_DIR/current.jpg}"

if [ ! -f "$WALLPAPER" ]; then
    notify-send "Theme" "Wallpaper not found: $WALLPAPER" -u critical 2>/dev/null || true
    exit 1
fi

mkdir -p "$WAL_CACHE" "$PALETTE_ROOT"

# Serialize applies so rapid wallpaper switches can't interleave their writes.
exec 8>"$WAL_CACHE/.apply.lock"
flock 8

KEY=$(palette_key "$WALLPAPER") || exit 1
PALETTE="$PALETTE_ROOT/$KEY"

if [ ! -f "$PALETTE/colors.json" ]; then
    build_palette "$WALLPAPER" "$PALETTE" || exit 1
fi
touch "$PALETTE"   # mark as recently used for pruning

apply_palette "$PALETTE"
reload_ui
background_tasks
echo "--> Theme applied successfully."
