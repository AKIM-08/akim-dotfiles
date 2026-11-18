#!/usr/bin/env python3
"""dock-autohide.py - show the Dock theme's Waybar only while the pointer is at its edge.

Started by launch.sh with the Dock theme. Waybar starts hidden ("start_hidden" in the built
config); this asks Hyprland where the pointer is about ten times a second (through Hyprland's
socket, no process is started) and toggles Waybar's visibility with SIGUSR1:

    pointer touches the dock's edge (bottom, left or right)  -> the dock slides in
    pointer moves away from the dock for HIDE_DELAY seconds  -> it hides again
"""

import json
import os
import signal
import socket
import sys
import time
from pathlib import Path

HOME = Path.home()
LAYOUT = HOME / ".config" / "waybar" / "layout.json"

POLL = 0.1            # seconds between pointer checks
POLL_SHOWN = 0.06     # faster while the dock is shown (smoother hiding)
EDGE = 2              # px from the screen edge that reveal the dock
REVEAL_DWELL = 0.08   # the pointer must stay at the edge this long (no accidental reveals)
HIDE_DELAY = 0.6      # seconds away from the dock before it hides
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


def waybar_pid():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if Path("/proc", d, "comm").read_text().strip() == "waybar":
                    return int(d)
            except OSError:
                pass
    return None


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
    path = socket_path()
    if not path:
        sys.stderr.write("dock-autohide: Hyprland socket not found\n")
        return 1
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    edge, zone = read_layout()
    mons, mons_at = [], 0.0
    pid, pid_at = None, 0.0
    shown = False
    at_edge_since = None
    away_since = None

    def set_shown(v):
        nonlocal shown
        if v != shown and pid:
            try:
                os.kill(pid, signal.SIGUSR1)       # Waybar: toggle visibility
                shown = v
            except OSError:
                pass

    while True:
        now = time.monotonic()
        if now - pid_at > 1.0:
            pid_at = now
            new = waybar_pid()
            if new != pid:                          # Waybar (re)started: it starts hidden
                pid, shown = new, False
                edge, zone = read_layout()
        if now - mons_at > 3.0 or not mons:
            mons_at = now
            try:
                mons = monitors(path)
            except (OSError, ValueError, KeyError):
                mons = []
        try:
            x, y = (float(v) for v in hypr(path, "cursorpos").split(","))
        except (OSError, ValueError):
            time.sleep(1)
            path = socket_path() or path
            continue

        mon = next(((mx, my, mw, mh) for mx, my, mw, mh in mons
                    if mx <= x < mx + mw and my <= y < my + mh), None)
        if mon and pid:
            mx, my, mw, mh = mon
            dist = {"bottom": my + mh - 1 - y, "left": x - mx, "right": mx + mw - 1 - x}.get(edge, my + mh - 1 - y)
            if not shown:
                if dist <= EDGE:
                    at_edge_since = at_edge_since or now
                    if now - at_edge_since >= REVEAL_DWELL:
                        set_shown(True)
                        away_since = None
                else:
                    at_edge_since = None
            else:
                if dist > zone:
                    away_since = away_since or now
                    if now - away_since >= HIDE_DELAY:
                        set_shown(False)
                        at_edge_since = None
                else:
                    away_since = None
        time.sleep(POLL_SHOWN if shown else POLL)


if __name__ == "__main__":
    sys.exit(main())
