#!/usr/bin/env python3
"""cursors.py - mouse pointer: Breeze, in the size chosen in Settings -> Mouse & keyboard.

    cursors.py set <size>      switch to this size now and remember it (24, 28, 32, 40, ...)
    cursors.py restore         apply the remembered size (Hyprland start)
    cursors.py get             print "breeze <size>"

Hyprland keeps drawing the old pointer until something makes it reload, so a change is
applied as: load another theme for a moment, load Breeze at the new size, then move the pointer
onto its own position. The new size shows at once, without touching the mouse.
Apps that draw their own pointer (XWayland, a few GTK apps) take the size from GSettings and the
XCURSOR_* variables; already open ones may need to be reopened.
"""

import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CHOICE = HOME / ".config" / "hypr" / "cursor-theme"
THEME = "breeze_cursors"            # from the breeze-cursor-theme package
DEFAULT_SIZE = 28


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read_size() -> int:
    try:
        return int(CHOICE.read_text().split()[-1])
    except (OSError, ValueError, IndexError):
        return DEFAULT_SIZE


def apply(size: int):
    # A different theme first: Hyprland ignores setcursor with the theme it already has
    run("hyprctl", "setcursor", "Adwaita", str(size))
    run("hyprctl", "setcursor", THEME, str(size))
    for var, val in (("XCURSOR_THEME", THEME), ("XCURSOR_SIZE", str(size)), ("HYPRCURSOR_SIZE", str(size))):
        run("hyprctl", "keyword", "env", f"{var},{val}")
    # GTK apps follow these live
    run("gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", THEME)
    run("gsettings", "set", "org.gnome.desktop.interface", "cursor-size", str(size))
    # XWayland apps read the default theme from here when they start
    d = HOME / ".icons" / "default"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.theme").write_text(f"[Icon Theme]\nName=Default\nInherits={THEME}\n")
    # Redraw the pointer where it is, so the new size shows without moving the mouse
    pos = run("hyprctl", "cursorpos").replace(" ", "")
    if "," in pos:
        x, y = pos.split(",")[:2]
        run("hyprctl", "dispatch", "movecursor", x, y)


def main(argv):
    cmd = argv[0] if argv else "restore"
    if cmd == "get":
        print("breeze", read_size())
        return 0
    if cmd == "set":
        try:
            size = int(argv[-1]) if len(argv) > 1 else read_size()   # "set 32" (also "set breeze 32")
        except ValueError:
            print("usage: cursors.py set <size>", file=sys.stderr)
            return 2
        size = max(16, min(96, size))
        CHOICE.parent.mkdir(parents=True, exist_ok=True)
        CHOICE.write_text(f"breeze {size}\n")
        apply(size)
        return 0
    if cmd == "restore":
        apply(read_size())
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
