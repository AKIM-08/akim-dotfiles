#!/usr/bin/env python3
"""screens.py - where other screens (HDMI, USB-C) go: next to the laptop, same picture, or alone.

    screens.py list                  connected screens, as JSON
    screens.py set <screen> <place>  right | left | above | mirror | only | off
    screens.py restore               re-apply the saved places (desktop-extras runs it when a screen
                                     is plugged in or out)

Places are kept per screen in ~/.config/hypr/screens.json and written as monitor lines in
user-settings.hl, so a screen gets its place back each time it is plugged in. Used by Settings ->
Display -> Screens, the screens menu (Super + Shift + D) and Quick Settings.

"only" (show everything on the other screen, laptop screen off) only turns the laptop screen off
while that screen is connected: unplugging it turns the laptop screen back on, and the "off" is never
written to the config, so starting without that screen never leaves the laptop black.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
HYPR = HOME / ".config" / "hypr"
STATE = HYPR / "screens.json"
USER_SETTINGS = HYPR / "user-settings.hl"
PLACES = [("right", "Right"), ("left", "Left"), ("above", "Above"), ("mirror", "Same picture"),
          ("only", "Only this one"), ("off", "Off")]


def hyprctl(*args):
    try:
        return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=4).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def monitors():
    try:
        return json.loads(hyprctl("-j", "monitors", "all") or "[]")
    except ValueError:
        return []


def internal_name(mons=None):
    for m in mons if mons is not None else monitors():
        if m.get("name", "").startswith(("eDP", "LVDS", "DSI")):
            return m["name"]
    return None


def externals(mons=None):
    mons = mons if mons is not None else monitors()
    inside = internal_name(mons)
    return [m for m in mons if m.get("name") != inside]


def describe(m):
    what = " ".join(x for x in (m.get("make"), m.get("model")) if x and x != "Unknown").strip()
    return what or m.get("name", "Screen")


def saved():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def line_for(name, place, inside):
    if place == "off":
        return f"{name}, disable"
    if place == "mirror" and inside:
        return f"{name}, preferred, auto, 1, mirror, {inside}"
    pos = {"right": "auto-right", "left": "auto-left", "above": "auto-up"}.get(place, "auto-right")
    return f"{name}, preferred, {pos}, 1"


def set_block(content):
    """Same marked block as Settings / quick-settings.sh use in user-settings.hl."""
    begin, end = "# >>> quick-settings: screens", "# <<< quick-settings: screens"
    try:
        lines = USER_SETTINGS.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    out, skip = [], False
    for line in lines:
        if line == begin:
            skip = True
        if not skip:
            out.append(line)
        if line == end:
            skip = False
    if content:
        out += [begin, content, end]
    USER_SETTINGS.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_all(state=None):
    """Write the saved places to user-settings.hl and apply them to what is connected now."""
    state = saved() if state is None else state
    if not state:                            # nothing chosen yet: Hyprland's default placement
        set_block("")
        return
    mons = monitors()
    inside = internal_name(mons)
    connected = {m["name"] for m in mons}
    lines = [f"monitor = {line_for(n, p, inside)}" for n, p in state.items() if p != "only"]
    # "only": the laptop screen is off while that screen is connected (and only then)
    # Never saved as "laptop screen off": starting without that screen would leave it black.
    # desktop-extras.py re-applies it live at login and whenever a screen is plugged in or out.
    only = [n for n, p in state.items() if p == "only" and n in connected]
    lines += [f"monitor = {n}, preferred, auto, 1" for n, p in state.items() if p == "only"]
    if inside:
        lines.append(f"monitor = {inside}, preferred, auto, 1")
    inside_line = f"{inside}, disable" if only else f"{inside}, preferred, auto, 1"
    set_block("\n".join(lines))
    # live: externals first, so the desktop always has a screen
    for n, p in state.items():
        if n in connected:
            hyprctl("keyword", "monitor", f"{n}, preferred, auto, 1" if p == "only" else line_for(n, p, inside))
    if inside:
        hyprctl("keyword", "monitor", inside_line)


def set_place(name, place):
    if place not in dict(PLACES):
        raise SystemExit(f"unknown place: {place}")
    state = saved()
    state[name] = place
    if place == "only":                      # one "only" screen at a time
        for n in state:
            if n != name and state[n] == "only":
                state[n] = "right"
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    apply_all(state)


def main():
    a = sys.argv[1:]
    if a[:1] == ["list"]:
        print(json.dumps([{"name": m["name"], "what": describe(m), "internal": m["name"] == internal_name(),
                           "place": saved().get(m["name"])} for m in monitors()], indent=2))
    elif a[:1] == ["set"] and len(a) == 3 and re.fullmatch(r"[\w.-]+", a[1]):
        set_place(a[1], a[2])
    elif a[:1] == ["restore"]:
        apply_all()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
