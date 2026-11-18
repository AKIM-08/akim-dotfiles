#!/usr/bin/env python3
"""dock-autohide.py - show the Dock theme's Waybar only while the pointer is at its edge.

Started by launch.sh with the Dock theme. Waybar starts hidden ("start_hidden" in the built
config). About ten times a second this asks Hyprland (through its socket, no process is started)
where the pointer is and on which layer Waybar's dock sits: shown it is on the overlay layer,
hidden on the bottom layer (the "modes" in config-dock). When that differs from what it should
be, Waybar gets SIGUSR1 (toggle). Reading the real state every time means the dock can't get
stuck shown or hidden, even after Waybar restarts or misses a toggle.

    pointer touches the dock's edge (top, bottom, left or right)  -> the dock slides in
    pointer moves away from the dock for HIDE_DELAY seconds       -> it hides again
"""

import fcntl
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path

HOME = Path.home()
LAYOUT = HOME / ".config" / "waybar" / "layout.json"
LOCK = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "dock-autohide.lock"

POLL = 0.1            # seconds between pointer checks
POLL_SHOWN = 0.06     # faster while the dock is shown (smoother hiding)
EDGE = 2              # px from the screen edge that reveal the dock
REVEAL_DWELL = 0.08   # the pointer must stay at the edge this long (no accidental reveals)
HIDE_DELAY = 0.6      # seconds away from the dock before it hides
SETTLE = 0.35         # after a toggle, wait this long before checking the dock's state again
# How far from the edge the pointer may go while the dock stays shown, per bar size
ZONE = {"compact": 72, "normal": 84, "large": 100}


def socket_path():
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    for base in (Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())) / "hypr", Path("/tmp/hypr")):
        p = base / sig / ".socket.sock"
        if sig and p.exists():
            return str(p)
    return None


def hypr(path, cmd: str) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        s.connect(path)
        s.sendall(cmd.encode())
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    return b"".join(chunks).decode(errors="replace")


def dock_state(path):
    """(pid, shown) of Waybar's layer surface, or (None, None) when Waybar isn't mapped."""
    for mon in json.loads(hypr(path, "j/layers")).values():
        for level, surfaces in mon.get("levels", {}).items():
            for s in surfaces:
                if s.get("namespace") == "waybar":
                    return s.get("pid"), str(level) in ("2", "3")     # top / overlay = shown
    return None, None


def read_layout():
    try:
        st = json.loads(LAYOUT.read_text(encoding="utf-8"))
        return st.get("position", "bottom"), ZONE.get(st.get("size", "normal"), 84)
    except (OSError, ValueError):
        return "bottom", 84


def monitors(path):
    out = []
    for m in json.loads(hypr(path, "j/monitors")):
        scale = m.get("scale", 1) or 1
        w, h = m["width"] / scale, m["height"] / scale
        if m.get("transform", 0) in (1, 3, 5, 7):
            w, h = h, w
        out.append((m["x"], m["y"], w, h))
    return out


def main():
    # Only one helper at a time (two would undo each other's toggles)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0
    path = socket_path()
    if not path:
        sys.stderr.write("dock-autohide: Hyprland socket not found\n")
        return 1
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    edge, zone = read_layout()
    layout_at = time.monotonic()
    mons, mons_at = [], 0.0
    want = False                  # should the dock be shown?
    at_edge_since = None
    away_since = None
    toggled_at = 0.0
    shown_at_toggle = None
    misses = 0                    # toggles after which Waybar's layer did not change
    blind = False                 # fallback: this Waybar ignores "modes", track the state here
    believed, blind_pid = False, None

    while True:
        now = time.monotonic()
        if now - layout_at > 2.0:
            layout_at = now
            edge, zone = read_layout()
        if now - mons_at > 3.0 or not mons:
            mons_at = now
            try:
                mons = monitors(path)
            except (OSError, ValueError, KeyError):
                mons = []
        try:
            x, y = (float(v) for v in hypr(path, "cursorpos").split(","))
            pid, shown = dock_state(path)
        except (OSError, ValueError, AttributeError):
            time.sleep(1)
            path = socket_path() or path
            continue

        mon = next(((mx, my, mw, mh) for mx, my, mw, mh in mons
                    if mx <= x < mx + mw and my <= y < my + mh), None)
        if mon:
            mx, my, mw, mh = mon
            dist = {"bottom": my + mh - 1 - y, "top": y - my, "left": x - mx,
                    "right": mx + mw - 1 - x}.get(edge, my + mh - 1 - y)
            if not want:
                if dist <= EDGE:
                    at_edge_since = at_edge_since or now
                    if now - at_edge_since >= REVEAL_DWELL:
                        want, away_since = True, None
                else:
                    at_edge_since = None
            else:
                if dist > zone:
                    away_since = away_since or now
                    if now - away_since >= HIDE_DELAY:
                        want, at_edge_since = False, None
                else:
                    away_since = None

        if blind:
            if pid != blind_pid:                  # Waybar (re)started: it starts hidden
                blind_pid, believed = pid, False
            if pid and believed != want and now - toggled_at > SETTLE:
                try:
                    os.kill(int(pid), signal.SIGUSR1)
                    believed, toggled_at = want, now
                except (OSError, ValueError):
                    pass
        # Make Waybar match: toggle only when its real state differs (and has settled)
        elif pid and shown is not None and shown != want and now - toggled_at > SETTLE:
            misses = misses + 1 if shown_at_toggle is not None and shown == shown_at_toggle else 0
            if misses >= 3:
                # The layer never changes, so it can't tell shown from hidden: restart Waybar
                # (it starts hidden) and keep track of the toggles from here on
                sys.stderr.write("dock-autohide: Waybar ignores \"modes\"; tracking toggles instead\n")
                blind, blind_pid, believed = True, None, False
                os.system("pkill -x waybar; sleep 0.3; setsid -f waybar >/dev/null 2>&1")
                toggled_at = time.monotonic() + 1.0
                continue
            try:
                os.kill(int(pid), signal.SIGUSR1)
                toggled_at, shown_at_toggle = now, shown
            except (OSError, ValueError):
                pass
        elif shown == want:
            misses, shown_at_toggle = 0, None
        time.sleep(POLL_SHOWN if want else POLL)


if __name__ == "__main__":
    sys.exit(main())
