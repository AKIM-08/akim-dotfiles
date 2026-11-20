#!/usr/bin/env python3
"""overview.py - every open window as a picture (Alt + Tab).

Two looks, chosen in Settings -> Appearance -> Menus (~/.config/hypr/overview-style):
    carousel   slanted cards, the chosen window large in the middle (default)
    grid       every window on one screen

Hold Alt and tap Tab to move (Shift + Tab goes back), let go of Alt to jump to that window: a quick
Alt + Tab goes back to the previous window. Arrows move too, Enter or a click jumps, typing keeps
only the windows whose app or title match, 1 - 9 / the chips show one workspace, Esc closes.

Windows on the workspace you're on are shown live; the others as they looked the last time you were
on their workspace (desktop-extras.py takes that picture a second after you arrive), or their icon.

Normally shown by desktop-extras.py (already running, so it opens at once): overview.sh writes
"overview" to its FIFO. Run on its own (python3 overview.py) when desktop-extras isn't running.
"""

import cairo
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk   # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell                # noqa: E402
except (ImportError, ValueError):
    GtkLayerShell = None

HOME = Path.home()
CACHE = HOME / ".cache" / "overview"
COLORS = HOME / ".cache" / "wal" / "colors.json"
SNAP_SCALE = 0.4
STYLE_FILE = HOME / ".config" / "hypr" / "overview-style"


def read_style():
    try:
        v = STYLE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        v = ""
    return v if v in ("carousel", "grid") else "carousel"


def rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


# ------------------------------------------------------------------------------ Hyprland
def hypr_socket(name):
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    for base in (Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "hypr", Path("/tmp/hypr")):
        p = base / sig / name
        if sig and p.exists():
            return str(p)
    return None


def hypr(cmd):
    path = hypr_socket(".socket.sock")
    if not path:
        return ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            s.connect(path)
            s.sendall(cmd.encode())
            out = b""
            while True:
                b = s.recv(65536)
                if not b:
                    break
                out += b
        return out.decode(errors="replace")
    except OSError:
        return ""


def hypr_json(cmd, default):
    try:
        return json.loads(hypr("j/" + cmd) or "null") or default
    except ValueError:
        return default


def focused_monitor():
    mons = hypr_json("monitors", [])
    return next((m for m in mons if m.get("focused")), mons[0] if mons else None)


def grab(mon, scale, fmt="ppm", path=None):
    """A picture of one screen (grim), as a pixbuf; saved to path instead when given."""
    if not mon:
        return None
    cmd = ["grim", "-o", mon["name"], "-s", str(scale), "-t", fmt]
    if fmt == "jpeg":
        cmd += ["-q", "70"]
    cmd.append(str(path) if path else "-")
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if path or r.returncode != 0 or not r.stdout:
        return None
    loader = GdkPixbuf.PixbufLoader()
    try:
        loader.write(r.stdout)
        loader.close()
        return loader.get_pixbuf()
    except GLib.Error:
        return None


def snapshot_workspace(ws_id):
    """Save how the windows of the workspace on screen look now (desktop-extras, on arrival)."""
    mon = focused_monitor()
    if not mon or mon.get("activeWorkspace", {}).get("id") != ws_id:
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    img = CACHE / f"ws-{ws_id}.jpg"
    grab(mon, SNAP_SCALE, "jpeg", img)
    wins = {c["address"]: c["at"] + c["size"] for c in hypr_json("clients", [])
            if c.get("workspace", {}).get("id") == ws_id and not c.get("hidden")}
    (CACHE / f"ws-{ws_id}.json").write_text(json.dumps({"mon": monitor_box(mon), "wins": wins}))


def monitor_box(mon):
    s = mon.get("scale") or 1
    return [mon["x"], mon["y"], mon["width"] / s, mon["height"] / s]


def crop(pix, box, at, size):
    """The part of a screen picture where a window was."""
    if pix is None:
        return None
    k = pix.get_width() / box[2]
    x, y = (at[0] - box[0]) * k, (at[1] - box[1]) * k
    w, h = size[0] * k, size[1] * k
    x, y = max(0, int(x)), max(0, int(y))
    w = int(min(w, pix.get_width() - x))
    h = int(min(h, pix.get_height() - y))
    if w < 4 or h < 4:
        return None
    return pix.new_subpixbuf(x, y, w, h)


def app_icon(cls, size):
    theme = Gtk.IconTheme.get_default()
    for n in (cls, cls.lower(), cls.lower().split(".")[-1]):
        try:
            info = Gio.DesktopAppInfo.new(n + ".desktop")
        except TypeError:
            info = None
        if info and info.get_icon():
            ic = theme.lookup_by_gicon(info.get_icon(), size, Gtk.IconLookupFlags.FORCE_SIZE)
            if ic:
                try:
                    return ic.load_icon()
                except GLib.Error:
                    pass
        if theme.has_icon(n):
            try:
                return theme.load_icon(n, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except GLib.Error:
                pass
    try:
        return theme.load_icon("application-x-executable", size, Gtk.IconLookupFlags.FORCE_SIZE)
    except GLib.Error:
        return None


def palette():
    c = {"bg": "#141824", "fg": "#eef1f7", "accent": "#7aa2f7"}
    try:
        d = json.loads(COLORS.read_text(encoding="utf-8"))
        c = {"bg": d["special"]["background"], "fg": d["special"]["foreground"], "accent": d["colors"]["color1"]}
    except (OSError, ValueError, KeyError):
        pass
    return c


def rgba(h, a):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def ink(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return "#101010" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else "#ffffff"


# ------------------------------------------------------------------------------ the window
class Overview(Gtk.Window):
    def __init__(self, standalone=False):
        super().__init__()
        self.standalone = standalone
        self.set_app_paintable(True)
        if self.get_screen().get_rgba_visual():
            self.set_visual(self.get_screen().get_rgba_visual())
        if GtkLayerShell:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "overview")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_exclusive_zone(self, -1)
            for e in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, e, True)
        else:
            self.fullscreen()
        self.provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        root = Gtk.EventBox()
        root.get_style_context().add_class("ov-backdrop")
        root.connect("button-press-event", lambda *_: (self.close_overview(), True)[1])
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        col.set_margin_top(36)
        col.set_margin_bottom(36)
        col.set_margin_start(48)
        col.set_margin_end(48)
        self.search = Gtk.Label(xalign=0.5)
        self.search.get_style_context().add_class("ov-search")
        self.search.set_halign(Gtk.Align.CENTER)
        self.chips = Gtk.Box(spacing=8)
        self.chips.set_halign(Gtk.Align.CENTER)
        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(22)
        self.grid.set_column_spacing(22)
        self.grid.set_halign(Gtk.Align.CENTER)
        self.grid.set_valign(Gtk.Align.CENTER)
        self.empty = Gtk.Label(label="No windows open")
        self.empty.get_style_context().add_class("ov-empty")
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.canvas = Gtk.DrawingArea()
        self.canvas.connect("draw", self.draw_carousel)
        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK |
                               Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.canvas.connect("button-press-event", self.on_canvas_click)
        self.canvas.connect("scroll-event", self.on_scroll)
        holder.pack_start(self.canvas, True, True, 0)
        holder.pack_start(self.grid, True, True, 0)
        holder.pack_start(self.empty, True, True, 0)
        col.pack_start(self.search, False, False, 0)
        col.pack_start(self.chips, False, False, 0)
        col.pack_start(holder, True, True, 0)
        hint = self.hint = Gtk.Label(label="Hold Alt, Tab to move · let go to jump · type to find · 1 – 9 a workspace · Esc closes")
        hint.get_style_context().add_class("ov-hint")
        col.pack_start(hint, False, False, 0)
        root.add(col)
        self.add(root)
        self.connect("key-press-event", self.on_key)
        self.connect("key-release-event", self.on_release)
        self.wins, self.shown, self.tiles = [], [], []
        self.sel = 0
        self.text = ""
        self.ws_filter = None
        self.sticky = False
        self.opened = 0
        self.style = "carousel"
        self.pos = 0.0                  # carousel: animated position (follows self.sel)
        self.anim = None
        self.icons = {}

    # -------------------------------------------------------------- open / close
    def open(self):
        if self.get_visible():
            self.move(1)
            return
        self.css()
        mon = focused_monitor()
        live = grab(mon, 0.5) if mon else None             # before showing, so we're not in it
        box = monitor_box(mon) if mon else None
        cur_ws = mon.get("activeWorkspace", {}).get("id") if mon else None
        clients = [c for c in hypr_json("clients", []) if c.get("mapped", True) and not c.get("hidden")
                   and c.get("workspace", {}).get("id", -1) > 0 and c.get("class") != "dotfiles-settings-overlay"]
        clients.sort(key=lambda c: c.get("focusHistoryID", 99))
        snaps = {}
        self.wins = []
        for c in clients:
            ws = c["workspace"]["id"]
            pix = None
            if ws == cur_ws and live is not None:
                pix = crop(live, box, c["at"], c["size"])
            else:
                if ws not in snaps:
                    snaps[ws] = self.load_snapshot(ws)
                img, meta = snaps[ws]
                geo = meta.get("wins", {}).get(c["address"]) if meta else None
                if img is not None and geo:
                    pix = crop(img, meta["mon"], geo[:2], geo[2:])
            self.wins.append({"address": c["address"], "class": c.get("class") or "", "title": c.get("title") or "",
                              "ws": ws, "ws_name": c["workspace"].get("name", str(ws)), "pix": pix,
                              "size": c["size"]})
        self.text, self.ws_filter, self.sticky = "", None, False
        self.style = read_style()
        self.sel = 1 if len(self.wins) > 1 else 0
        self.pos = float(self.sel)
        self.opened = time.monotonic()
        self.rebuild()
        self.show_all()
        self.canvas.set_visible(self.style == "carousel")
        self.grid.set_visible(self.style == "grid")
        self.update_search()
        self.empty.set_visible(not self.shown)
        self.present()

    def load_snapshot(self, ws):
        try:
            meta = json.loads((CACHE / f"ws-{ws}.json").read_text())
            img = GdkPixbuf.Pixbuf.new_from_file(str(CACHE / f"ws-{ws}.jpg"))
            return img, meta
        except (OSError, ValueError, GLib.Error):
            return None, None

    def close_overview(self):
        self.hide()
        self.wins, self.shown, self.tiles = [], [], []
        for c in self.grid.get_children():
            self.grid.remove(c)
        if self.standalone:
            Gtk.main_quit()

    def jump(self):
        if not self.shown:
            return self.close_overview()
        w = self.shown[self.sel]
        self.close_overview()
        GLib.timeout_add(40, lambda: (hypr(f"dispatch focuswindow address:{w['address']}"), False)[1])

    # -------------------------------------------------------------- drawing
    def css(self):
        p = palette()
        a, b, f = p["accent"], p["bg"], p["fg"]
        self.provider.load_from_data(f"""
        .ov-backdrop {{ background: {rgba(b, 0.55)}; }}
        .ov-search {{ background: {rgba(f, 0.10)}; border: 1px solid {rgba(f, 0.16)}; border-radius: 999px;
                      padding: 8px 22px; color: {f}; font-size: 14px; min-width: 320px; }}
        .ov-search.idle {{ color: {rgba(f, 0.55)}; }}
        .ov-chip {{ background: {rgba(f, 0.08)}; color: {f}; border-radius: 999px; padding: 4px 14px;
                    font-family: "JetBrainsMono Nerd Font", monospace; font-weight: 700; font-size: 12px; }}
        .ov-chip.on {{ background: {a}; color: {ink(a)}; }}
        .ov-tile {{ background: {rgba(b, 0.70)}; border: 2px solid {rgba(f, 0.10)}; border-radius: 14px; padding: 8px; }}
        .ov-tile.sel {{ border-color: {a}; background: {rgba(a, 0.18)}; }}
        .ov-cap {{ color: {f}; font-size: 12px; font-weight: 600; }}
        .ov-ws {{ color: {a}; font-family: "JetBrainsMono Nerd Font", monospace; font-weight: 800; font-size: 11px; }}
        .ov-empty {{ color: {rgba(f, 0.6)}; font-size: 16px; }}
        .ov-hint {{ color: {rgba(f, 0.55)}; font-size: 12px; }}
        """.encode())

    def matches(self, w):
        if self.ws_filter is not None and w["ws"] != self.ws_filter:
            return False
        hay = f"{w['class']} {w['title']}".lower()
        return all(t in hay for t in self.text.lower().split())

    def rebuild(self):
        for c in self.grid.get_children():
            self.grid.remove(c)
        for c in self.chips.get_children():
            self.chips.remove(c)
        spaces = sorted({w["ws"] for w in self.wins})
        for ws in [None] + spaces:
            chip = Gtk.EventBox()
            lbl = Gtk.Label(label="All" if ws is None else str(ws))
            lbl.get_style_context().add_class("ov-chip")
            if ws == self.ws_filter:
                lbl.get_style_context().add_class("on")
            chip.add(lbl)
            chip.connect("button-press-event", lambda *_, v=ws: (self.set_ws(v), True)[1])
            self.chips.pack_start(chip, False, False, 0)
        self.chips.show_all()
        self.shown = [w for w in self.wins if self.matches(w)]
        self.sel = max(0, min(self.sel, len(self.shown) - 1))
        n = len(self.shown)
        self.tiles = []
        if self.style == "carousel":
            self.pos = min(self.pos, max(0, n - 1))
            self.empty.set_visible(n == 0)
            self.canvas.queue_draw()
            return
        if n:
            geo = self.get_screen().get_monitor_geometry(0) if self.get_screen() else None
            sw, sh = (geo.width, geo.height) if geo else (1920, 1080)
            area_w, area_h = sw - 96, sh - 230
            cols = max(1, min(n, math.ceil(math.sqrt(n * area_w / area_h / 1.6))))
            rows = math.ceil(n / cols)
            cell_w = min(520, (area_w - 22 * (cols - 1)) / cols - 20)
            cell_h = min(360, (area_h - 22 * (rows - 1)) / rows - 46)
            for i, w in enumerate(self.shown):
                tile = self.make_tile(w, cell_w, cell_h)
                self.grid.attach(tile, i % cols, i // cols, 1, 1)
                self.tiles.append(tile)
            self.cols = cols
        self.grid.show_all()
        self.empty.set_visible(n == 0)
        self.highlight()

    def make_tile(self, w, cw, ch):
        ev = Gtk.EventBox()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("ov-tile")
        pix = w["pix"]
        if pix is not None:
            k = min(cw / pix.get_width(), ch / pix.get_height())
            img = Gtk.Image.new_from_pixbuf(pix.scale_simple(max(1, int(pix.get_width() * k)),
                                                             max(1, int(pix.get_height() * k)),
                                                             GdkPixbuf.InterpType.BILINEAR))
        else:
            icon = app_icon(w["class"], int(min(cw, ch) * 0.35))
            img = Gtk.Image.new_from_pixbuf(icon) if icon else Gtk.Image()
            img.set_size_request(int(cw), int(min(ch, cw * 0.56)))
        box.pack_start(img, True, True, 0)
        cap = Gtk.Box(spacing=8)
        icon = app_icon(w["class"], 18)
        if icon:
            cap.pack_start(Gtk.Image.new_from_pixbuf(icon), False, False, 0)
        name = w["class"].split(".")[-1].capitalize() or "Window"
        lbl = Gtk.Label(label=f"{name} · {w['title']}" if w["title"] and w["title"] != name else name, xalign=0)
        lbl.set_ellipsize(3)
        lbl.set_max_width_chars(max(10, int(cw / 8)))
        lbl.get_style_context().add_class("ov-cap")
        cap.pack_start(lbl, True, True, 0)
        wsl = Gtk.Label(label=str(w["ws"]))
        wsl.get_style_context().add_class("ov-ws")
        cap.pack_end(wsl, False, False, 0)
        box.pack_start(cap, False, False, 0)
        ev.add(box)
        ev.connect("button-press-event", lambda *_, addr=w["address"]: (self.click(addr), True)[1])
        ev.box = box
        return ev

    def highlight(self):
        if self.style == "carousel":
            self.start_anim()
            return
        for i, t in enumerate(self.tiles):
            ctx = t.box.get_style_context()
            (ctx.add_class if i == self.sel else ctx.remove_class)("sel")

    def update_search(self):
        ctx = self.search.get_style_context()
        if self.text:
            self.search.set_text(self.text)
            ctx.remove_class("idle")
        else:
            self.search.set_text("Type to find a window")
            ctx.add_class("idle")

    # -------------------------------------------------------------- input
    def click(self, addr):
        self.sel = next((i for i, w in enumerate(self.shown) if w["address"] == addr), 0)
        self.jump()

    def set_ws(self, ws):
        self.ws_filter = ws
        self.sticky = True
        self.sel = 0
        self.rebuild()

    def move(self, step):
        if self.shown:
            self.sel = (self.sel + step) % len(self.shown)
            self.highlight()

    def on_key(self, _w, e):
        k = e.keyval
        shift = e.state & Gdk.ModifierType.SHIFT_MASK
        if k == Gdk.KEY_Escape:
            self.close_overview()
        elif k in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            self.move(-1 if (shift or k == Gdk.KEY_ISO_Left_Tab) else 1)
        elif k in (Gdk.KEY_Right, Gdk.KEY_Left):
            self.sticky = True
            self.move(1 if k == Gdk.KEY_Right else -1)
        elif k in (Gdk.KEY_Down, Gdk.KEY_Up):
            self.sticky = True
            step = 1 if self.style == "carousel" else getattr(self, "cols", 1)
            self.move(step * (1 if k == Gdk.KEY_Down else -1))
        elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.jump()
        elif k == Gdk.KEY_BackSpace:
            self.sticky = True
            self.text = self.text[:-1]
            self.update_search()
            self.sel = 0
            self.rebuild()
        else:
            ch = Gdk.keyval_to_unicode(k)
            if ch and chr(ch).isdigit() and chr(ch) != "0" and not self.text:
                ws = int(chr(ch))
                self.set_ws(ws if any(w["ws"] == ws for w in self.wins) else None)
            elif ch and chr(ch).isprintable():
                self.sticky = True
                self.text += chr(ch)
                self.update_search()
                self.sel = 0
                self.rebuild()
        return True

    # -------------------------------------------------------------- carousel
    def start_anim(self):
        if self.anim is None:
            self.anim = self.canvas.add_tick_callback(self.step_anim)
        self.canvas.queue_draw()

    def step_anim(self, *_):
        d = self.sel - self.pos
        self.pos += d * 0.28
        if abs(d) < 0.004:
            self.pos = float(self.sel)
            self.canvas.queue_draw()
            self.anim = None
            return False
        self.canvas.queue_draw()
        return True

    def icon_for(self, cls, size):
        key = (cls, size)
        if key not in self.icons:
            self.icons[key] = app_icon(cls, size)
        return self.icons[key]

    def card_geometry(self, W, H):
        cw = min(W * 0.42, H * 0.62 * 16 / 9)
        return cw, cw * 9 / 16, W / 2, H * 0.46

    def draw_carousel(self, _w, cr):
        if self.style != "carousel" or not self.shown:
            return False
        W, H = self.canvas.get_allocated_width(), self.canvas.get_allocated_height()
        p = palette()
        acc = tuple(int(p["accent"].lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        cw, ch, cx, cy = self.card_geometry(W, H)
        n = len(self.shown)
        near = [i for i in range(n) if abs(i - self.pos) < 3.4]
        for i in sorted(near, key=lambda i: -abs(i - self.pos)):          # far ones first
            d = i - self.pos
            ad = min(abs(d), 3.4)
            s = 1 - ad * 0.17
            alpha = max(0.0, 1 - ad * 0.24)
            cr.save()
            cr.translate(cx + d * W * 0.2, cy)
            cr.transform(cairo.Matrix(1, 0, -0.14 * max(-1, min(1, d)), 1, 0, 0))   # slant, toward the middle
            cr.scale(s, s)
            self.draw_card(cr, self.shown[i], -cw / 2, -ch / 2, cw, ch, alpha, abs(d) < 0.5, acc)
            cr.restore()
        w = self.shown[self.sel]
        name = w["class"].split(".")[-1].capitalize() or "Window"
        self.draw_text(cr, f"{name} · {w['title']}" if w["title"] and w["title"] != name else name,
                       W / 2, cy + ch / 2 + 48, 20, 1.0, True)
        self.draw_text(cr, f"workspace {w['ws_name']}   ·   {self.sel + 1} / {n}", W / 2, cy + ch / 2 + 78, 13, 0.7, False)
        return False

    def draw_card(self, cr, w, x, y, cw, ch, alpha, chosen, acc):
        cr.push_group()
        rounded(cr, x, y, cw, ch, 18)
        cr.set_source_rgba(0.07, 0.08, 0.12, 0.92)
        cr.fill_preserve()
        cr.save()
        cr.clip()
        pix = w["pix"]
        if pix is not None:
            k = min(cw / pix.get_width(), ch / pix.get_height())          # whole window, centered
            pw, ph = pix.get_width() * k, pix.get_height() * k
            cr.translate(x + (cw - pw) / 2, y + (ch - ph) / 2)
            cr.scale(k, k)
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint()
        else:
            icon = self.icon_for(w["class"], int(ch * 0.4))
            if icon is not None:
                Gdk.cairo_set_source_pixbuf(cr, icon, x + (cw - icon.get_width()) / 2, y + (ch - icon.get_height()) / 2)
                cr.paint()
        cr.restore()
        if chosen:
            rounded(cr, x - 3, y - 3, cw + 6, ch + 6, 21)
            cr.set_source_rgba(*acc, 1)
            cr.set_line_width(4)
            cr.stroke()
        cr.pop_group_to_source()
        cr.paint_with_alpha(alpha)

    def draw_text(self, cr, text, x, y, size, alpha, bold):
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        if len(text) > 90:
            text = text[:88] + "…"
        ext = cr.text_extents(text)
        cr.move_to(x - ext.width / 2 - ext.x_bearing, y)
        cr.set_source_rgba(0, 0, 0, 0.5 * alpha)
        cr.rel_move_to(0, 1)
        cr.show_text(text)
        cr.move_to(x - ext.width / 2 - ext.x_bearing, y)
        cr.set_source_rgba(1, 1, 1, alpha)
        cr.show_text(text)

    def on_canvas_click(self, _w, e):
        if not self.shown:
            return True
        W = self.canvas.get_allocated_width()
        cw, ch, cx, cy = self.card_geometry(W, self.canvas.get_allocated_height())
        if abs(e.x - cx) <= cw / 2 and abs(e.y - cy) <= ch / 2:
            self.jump()                                  # the big one in the middle
        else:
            step = round((e.x - cx) / (W * 0.2))
            if step:
                self.sticky = True
                self.sel = max(0, min(len(self.shown) - 1, self.sel + step))
                self.highlight()
        return True

    def on_scroll(self, _w, e):
        dx = dy = 0
        ok, dx, dy = e.get_scroll_deltas() if e.direction == Gdk.ScrollDirection.SMOOTH else (False, 0, 0)
        if e.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT) or dy > 0.3 or dx > 0.3:
            self.sticky = True
            self.move(1)
        elif e.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT) or dy < -0.3 or dx < -0.3:
            self.sticky = True
            self.move(-1)
        return True

    def on_release(self, _w, e):
        # Letting go of Alt jumps, unless you started typing / using arrows / chips
        if e.keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Meta_L) and not self.sticky:
            self.jump()
        return True


def main():
    win = Overview(standalone=True)
    win.connect("destroy", Gtk.main_quit)
    win.open()
    Gtk.main()


if __name__ == "__main__":
    main()
