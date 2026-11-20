#!/usr/bin/env python3
"""apply-papirus-color.py - folder icons in the wallpaper's color, without touching system files.

Builds a small private icon theme, ~/.local/share/icons/Papirus-Akim, that inherits Papirus-Dark
and only holds the folder icons: links to the Papirus folder icons of the color closest to the
wallpaper accent (blue, teal, orange...). Recoloring just rewrites those links, so the system
icon folders stay read-only (no papirus-folders, no sudo, no chmod).

    apply-papirus-color.py          recolor from ~/.cache/wal/colors.json (skips if unchanged)
    apply-papirus-color.py --force  rebuild even if the color is the same
"""

import configparser
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
NAME = "Papirus-Akim"
OUT = HOME / ".local" / "share" / "icons" / NAME
STAMP = OUT / ".color"
BASES = [HOME / ".local" / "share" / "icons", HOME / ".icons", Path("/usr/local/share/icons"), Path("/usr/share/icons")]

# Papirus folder colors and their approximate RGB
PAPIRUS_COLORS = {
    "red": (244, 67, 54), "pink": (233, 30, 99), "violet": (156, 39, 176), "indigo": (103, 58, 183),
    "blue": (33, 150, 243), "cyan": (3, 169, 244), "darkcyan": (0, 188, 212), "teal": (0, 150, 136),
    "green": (76, 175, 80), "yellow": (255, 235, 59), "orange": (255, 152, 0), "brown": (121, 85, 72),
    "grey": (158, 158, 158), "bluegrey": (96, 125, 139), "black": (0, 0, 0), "white": (255, 255, 255),
    "nord": (136, 192, 208),
}


def closest_color():
    try:
        accent = json.loads((HOME / ".cache" / "wal" / "colors.json").read_text(encoding="utf-8"))["colors"]["color4"]
        rgb = tuple(int(accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except (OSError, ValueError, KeyError):
        return "blue"
    return min(PAPIRUS_COLORS, key=lambda n: math.dist(rgb, PAPIRUS_COLORS[n]))


def find_theme(name):
    for base in BASES:
        p = base / name
        if (p / "index.theme").is_file():
            return p
    return None


def read_index(path):
    ini = configparser.ConfigParser(interpolation=None, strict=False)
    ini.optionxform = str
    try:
        ini.read(path, encoding="utf-8")
    except configparser.Error:
        pass
    return ini


def build(color):
    themes = [t for t in (find_theme("Papirus-Dark"), find_theme("Papirus")) if t]
    if not themes:
        return False
    pattern = re.compile(rf"^((?:folder|user)-){re.escape(color)}((?:-.*)?\.svg)$")
    tmp = OUT.with_name(NAME + ".new")
    shutil.rmtree(tmp, ignore_errors=True)
    dirs = {}                                  # "48x48/places" -> index.theme section
    for theme in themes:
        index = read_index(theme / "index.theme")
        for sub in sorted(theme.iterdir()):
            places = sub / "places"
            rel = f"{sub.name}/places"
            if rel in dirs or not places.is_dir():
                continue
            links = []
            for f in places.iterdir():
                m = pattern.match(f.name)
                if m:
                    links.append((m.group(1).rstrip("-") + m.group(2), f))
            if not links:
                continue
            target = tmp / rel
            target.mkdir(parents=True, exist_ok=True)
            for plain, src in links:
                os.symlink(src, target / plain)
            dirs[rel] = dict(index[rel]) if index.has_section(rel) else {"Size": sub.name.split("x")[0], "Context": "Places", "Type": "Fixed"}
    if not dirs:
        shutil.rmtree(tmp, ignore_errors=True)
        return False
    lines = ["[Icon Theme]", f"Name={NAME}", "Comment=Papirus-Dark with folders in the wallpaper's color",
             "Inherits=Papirus-Dark,Papirus,breeze-dark,hicolor", "Directories=" + ",".join(dirs), ""]
    for rel, section in dirs.items():
        lines.append(f"[{rel}]")
        lines += [f"{k}={v}" for k, v in section.items()]
        lines.append("")
    (tmp / "index.theme").write_text("\n".join(lines), encoding="utf-8")
    (tmp / ".color").write_text(color + "\n", encoding="utf-8")
    if shutil.which("gtk-update-icon-cache"):
        subprocess.run(["gtk-update-icon-cache", "-q", "-f", "-t", str(tmp)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    old = OUT.with_name(NAME + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if OUT.exists():
        OUT.rename(old)
    tmp.rename(OUT)
    shutil.rmtree(old, ignore_errors=True)
    return True


def use_theme(refresh=True):
    """Make the desktop use Papirus-Akim (GTK settings files, gsettings, Qt, Rofi)."""
    files = [
        (HOME / ".config/gtk-3.0/settings.ini", r"^gtk-icon-theme-name=.*$", f"gtk-icon-theme-name={NAME}"),
        (HOME / ".config/gtk-4.0/settings.ini", r"^gtk-icon-theme-name=.*$", f"gtk-icon-theme-name={NAME}"),
        (HOME / ".config/qt5ct/qt5ct.conf", r"^icon_theme=.*$", f"icon_theme={NAME}"),
        (HOME / ".config/qt6ct/qt6ct.conf", r"^icon_theme=.*$", f"icon_theme={NAME}"),
        (HOME / ".config/rofi/config.rasi", r'icon-theme: "[^"]*";', f'icon-theme: "{NAME}";'),
        (HOME / ".config/rofi/launcher.rasi", r'icon-theme: "[^"]*";', f'icon-theme: "{NAME}";'),
    ]
    for path, pat, new in files:
        try:
            s = path.read_text(encoding="utf-8")
            t = re.sub(pat, new, s, flags=re.M)
            if t != s:
                path.write_text(t, encoding="utf-8")
        except OSError:
            pass
    if refresh and shutil.which("gsettings"):
        # Switching away and back makes running GTK apps (Nautilus...) reload the folder icons now
        for name in ("Papirus-Dark", NAME):
            subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)


def main():
    color = closest_color()
    try:
        same = STAMP.read_text(encoding="utf-8").strip() == color
    except OSError:
        same = False
    if same and "--force" not in sys.argv:
        use_theme(refresh=False)          # config files copied from the repo name Papirus-Dark
        return
    if build(color):
        use_theme()


if __name__ == "__main__":
    main()
