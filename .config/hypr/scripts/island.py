#!/usr/bin/env python3
"""island.py - Dynamic island: the whole top bar inside a notch (Waybar theme "Island").

Started by ~/.config/waybar/scripts/launch.sh instead of Waybar when the Island theme is chosen.
A black notch hangs from the screen edge chosen in Settings -> Waybar -> Position (top, bottom,
left or right; on the sides it is a tall, thin notch):

    at rest        workspace dots (click / scroll to switch), clock and date, a mini cover
                   with an equalizer while music plays, battery
    hover          grows into a panel: music with controls and progress, volume and brightness,
                   Wi-Fi, Bluetooth, night light, silent mode, power, settings, wallpapers
    volume and brightness keys   the clock turns into a level bar for a moment
    notifications  drop down from the notch for a few seconds (click: notification list)

The notch is drawn on a fixed transparent layer surface; only the notch itself takes the pointer
(input region), so clicks around it reach the windows. Volume and brightness levels arrive as the
OSD notifications volume-control.sh and brightness-control.sh already send; notifications are
read from the session bus with dbus-monitor, and SwayNC's own popups are paused while the island
runs (it keeps the notification list). System state comes from quickpanel.py's readers.
"""

import hashlib
import html
import json
import math
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quickpanel as qp                                        # noqa: E402  GTK setup + state readers
from quickpanel import Gdk, GdkPixbuf, GLib, Gtk, have, run, spawn   # noqa: E402

try:
    import cairo
except ImportError:
    sys.stderr.write("island: python3-cairo is missing\n")
    sys.exit(1)

if not qp.HAS_LAYER_SHELL:
    sys.stderr.write("island: gtk-layer-shell is missing (gir1.2-gtklayershell-0.1)\n")
    sys.exit(1)
from quickpanel import GtkLayerShell                           # noqa: E402

HOME = Path.home()
SCRIPTS = qp.SCRIPTS
WALLPAPERS = HOME / "Pictures" / "wallpapers"
THUMBS = HOME / ".cache" / "island" / "thumbs"
LAYOUT = HOME / ".config" / "waybar" / "layout.json"
COLORS = HOME / ".cache" / "wal" / "colors.json"
PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "island.pid"
INHIBITOR = "island"

# Notch height at rest and text size, per Waybar size (Settings -> Waybar -> Size)
SIZES = {"compact": (26, 11), "normal": (30, 12), "large": (34, 14)}

BATTERY_ICONS = ["\U000f0083", "\U000f007a", "\U000f007b", "\U000f007c", "\U000f007d", "\U000f007e",
                 "\U000f007f", "\U000f0080", "\U000f0081", "\U000f0082", "\U000f0079"]
ICON = {
    "volume": "\U000f057e", "muted": "\U000f075f", "brightness": "\U000f00df", "mic": "\U000f036c",
    "mic_off": "\U000f036d", "bell": "\U000f009a", "prev": "\U000f04ae", "next": "\U000f04ad",
    "play": "\U000f040a", "pause": "\U000f03e4", "wifi": "\U000f0928", "bt": "\U000f00af",
    "night": "\U000f0594", "silent": "\U000f009b", "power": "\U000f0425", "settings": "\U000f0493",
    "charging": "\U000f0084",
}
WS_EVENTS = {"workspace", "workspacev2", "createworkspace", "createworkspacev2", "destroyworkspace",
             "destroyworkspacev2", "moveworkspace", "moveworkspacev2", "focusedmon", "focusedmonv2",
             "openwindow", "closewindow", "movewindow", "movewindowv2"}


# ------------------------------------------------------------------------------ helpers
def cls(widget, *names):
    ctx = widget.get_style_context()
    for n in names:
        ctx.add_class(n)
    return widget


def set_cls(widget, name, on):
    ctx = widget.get_style_context()
    (ctx.add_class if on else ctx.remove_class)(name)


def label(text="", *classes, xalign=None):
    lab = Gtk.Label(label=text)
    if xalign is not None:
        lab.set_xalign(xalign)
    return cls(lab, *classes)


def flat_button(child_or_text, *classes):
    b = Gtk.Button()
    b.set_focus_on_click(False)
    b.set_can_focus(False)
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.add(label(child_or_text) if isinstance(child_or_text, str) else child_or_text)
    return cls(b, *classes)


def ease_out_back(t: float, s: float) -> float:
    t -= 1.0
    return t * t * ((s + 1) * t + s) + 1.0


def read_layout():
    """(notch height, text size, screen edge) from the Waybar choice in layout.json."""
    try:
        st = json.loads(LAYOUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    H, F = SIZES.get(st.get("size", "normal"), SIZES["normal"])
    edge = st.get("position", "top")
    return H, F, edge if edge in ("top", "bottom", "left", "right") else "top"


def load_palette() -> dict:
    c = {"accent": "#7fc3dd"}
    try:
        data = json.loads(COLORS.read_text(encoding="utf-8"))
        cols = data.get("colors", {})
        c["accent"] = cols.get("color9") or cols.get("color1") or c["accent"]
    except (OSError, ValueError):
        pass
    return c


def ink_for(hex_color: str) -> str:
    """Dark or light text, whichever reads better on this color."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return "#101010" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "#ffffff"


def hypr_socket(name: str):
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    for base in (Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())) / "hypr", Path("/tmp/hypr")):
        p = base / sig / name
        if sig and p.exists():
            return str(p)
    return None


def hypr(cmd: str) -> str:
    path = hypr_socket(".socket.sock")
    if not path:
        return ""
    try:
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
    except OSError:
        return ""


def read_battery():
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            cap = int((bat / "capacity").read_text().strip())
            charging = (bat / "status").read_text().strip() in ("Charging", "Full")
            return cap, charging
        except (OSError, ValueError):
            return None
    return None


def fill_pixbuf(pix, w: int, h: int):
    """Scale and center-crop a pixbuf to exactly w x h."""
    pw, ph = pix.get_width(), pix.get_height()
    s = max(w / pw, h / ph)
    sw, sh = max(w, round(pw * s)), max(h, round(ph * s))
    scaled = pix.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
    return scaled.new_subpixbuf((sw - w) // 2, (sh - h) // 2, w, h)


def load_fill(path: str, w: int, h: int):
    """Load an image file straight at about the needed size (fast for big wallpapers), then crop."""
    try:
        _fmt, pw, ph = GdkPixbuf.Pixbuf.get_file_info(path)
        if pw and ph:
            s = max(w / pw, h / ph)
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, max(w, round(pw * s)), max(h, round(ph * s)), True)
        else:
            pix = GdkPixbuf.Pixbuf.new_from_file(path)
        return fill_pixbuf(pix, w, h)
    except Exception:
        return None


def rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def hex_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


class WsDots(Gtk.DrawingArea):
    """Workspace dots: exact circles, the active one a short pill (animated), occupied ones
    brighter. Click a dot to go to that workspace."""

    def __init__(self, d, on_pick, vertical=False):
        super().__init__()
        self.vertical = vertical
        self.d = d
        self.gap = max(3, round(d * 0.7))
        self.long = round(d * 2.6)
        self.on_pick = on_pick
        self.ids, self.active, self.occupied = [], None, set()
        self.widths = {}
        self.hover = None
        self.accent = (0.5, 0.76, 0.87)
        self.tick_id = None
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("leave-notify-event", lambda *_: self.set_hover(None))

    def target(self, i):
        return self.long if i == self.active else self.d

    def set_state(self, ids, active, occupied):
        self.ids, self.active, self.occupied = ids, active, occupied
        for i in ids:
            self.widths.setdefault(i, float(self.target(i)))
        total = sum(self.target(i) for i in ids) + self.gap * max(0, len(ids) - 1)
        if self.vertical:
            self.set_size_request(self.d + 4, total)
        else:
            self.set_size_request(total, self.d + 4)
        if self.tick_id is None:
            self.tick_id = self.add_tick_callback(self.on_tick)

    def on_tick(self, *_):
        done = True
        for i in self.ids:
            t, w = self.target(i), self.widths[i]
            w += (t - w) * 0.3
            if abs(t - w) < 0.3:
                w = float(t)
            else:
                done = False
            self.widths[i] = w
        self.queue_draw()
        if done:
            self.tick_id = None
            return False
        return True

    def spans(self):
        W = self.get_allocated_height() if self.vertical else self.get_allocated_width()
        total = sum(self.widths[i] for i in self.ids) + self.gap * max(0, len(self.ids) - 1)
        x = (W - total) / 2
        for i in self.ids:
            yield i, x, self.widths[i]
            x += self.widths[i] + self.gap

    def on_draw(self, _w, cr):
        across = (self.get_allocated_width() if self.vertical else self.get_allocated_height())
        y = (across - self.d) / 2
        for i, x, w in self.spans():
            if i == self.active:
                cr.set_source_rgba(*self.accent, 1)
            elif i == self.hover:
                cr.set_source_rgba(1, 1, 1, 0.95)
            else:
                cr.set_source_rgba(1, 1, 1, 0.68 if i in self.occupied else 0.26)
            if self.vertical:
                rounded_rect(cr, y, x, self.d, w, self.d / 2)
            else:
                rounded_rect(cr, x, y, w, self.d, self.d / 2)
            cr.fill()
        return False

    def at(self, ex):
        for i, x, w in self.spans():
            if x - self.gap / 2 <= ex <= x + w + self.gap / 2:
                return i
        return None

    def set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.queue_draw()
        return False

    def on_motion(self, _w, e):
        return self.set_hover(self.at(e.y if self.vertical else e.x))

    def on_press(self, _w, e):
        i = self.at(e.y if self.vertical else e.x)
        if e.button == 1 and i is not None:
            self.on_pick(i)
        return True


class RoundImage(Gtk.DrawingArea):
    """An image drawn with rounded corners (a circle when radius is None); a letter or a soft
    placeholder when there is no picture; an optional white outline (current wallpaper)."""

    def __init__(self, w, h, radius=None):
        super().__init__()
        self.w, self.h, self.radius = w, h, radius
        self.pix = None
        self.letter = ""
        self.color = (1, 1, 1, 0.12)
        self.outline = False
        self.set_size_request(w, h)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self.on_draw)

    def set_image(self, pix=None, letter="", color=None):
        self.pix, self.letter = pix, letter
        if color:
            self.color = color
        self.queue_draw()

    def on_draw(self, _w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        x, y = (W - self.w) / 2, (H - self.h) / 2
        r = self.h / 2 if self.radius is None else self.radius
        rounded_rect(cr, x, y, self.w, self.h, r)
        cr.save()
        cr.clip_preserve()
        if self.pix:
            sf = self.pix.get_width() / self.w
            cr.translate(x, y)
            cr.scale(1 / sf, 1 / sf)
            Gdk.cairo_set_source_pixbuf(cr, self.pix, 0, 0)
            cr.paint()
            cr.identity_matrix()
        else:
            cr.set_source_rgba(*self.color)
            cr.fill_preserve()
            if self.letter:
                cr.set_source_rgba(1, 1, 1, 0.95)
                cr.select_font_face("sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(self.h * 0.45)
                ext = cr.text_extents(self.letter)
                cr.move_to(x + (self.w - ext.width) / 2 - ext.x_bearing, y + (self.h - ext.height) / 2 - ext.y_bearing)
                cr.show_text(self.letter)
        cr.restore()
        if self.outline:
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.set_line_width(2)
            rounded_rect(cr, x + 1, y + 1, self.w - 2, self.h - 2, max(0, r - 1))
            cr.stroke()
        cr.new_path()
        return False


# ------------------------------------------------------------------------------ the island
class Island(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("island")
        self.H, self.F, self.edge = read_layout()
        H, F = self.H, self.F
        self.vertical = self.edge in ("left", "right")
        self.T = round(H * 1.4) if self.vertical else H    # notch thickness at rest
        # length along the edge at least; grows to fit workspaces, clock and battery
        self.REST_W = round(H * (6 if self.vertical else 11))
        self.PANEL_W = round(F * 48)
        self.NOTIF_W = round(self.REST_W * 1.2)
        self.EAR = round(H * 0.45)           # concave curves joining the notch to the top edge
        self.PAD = round(H * 0.45)
        self.palette = load_palette()
        self.colors_mtime = None
        self.css_provider = None
        self.apply_css()

        self.mode = "rest"
        self.hover = False
        self.level_until = 0.0
        self.notif_until = 0.0
        self.cur_w, self.cur_h = float(self.REST_W), float(H)
        self.anim = None
        self.tick_id = None
        self.expand_timer = None
        self.collapse_timer = None
        self.scroll_acc = 0.0
        self.ws_ids = []
        self.ws_pending = False
        self.media = None
        self.media_at = 0.0
        self.last_art = None
        self.eq_timer = None
        self.hold = {}
        self.state = {}
        self.slow_busy = self.fast_busy = False
        self.panel_timers = []
        self.walls_key = None
        self.wall_paths = []
        self.procs = []
        self.ticks = 0

        self.set_app_paintable(True)
        screen = self.get_screen()
        if screen.get_rgba_visual() and screen.is_composited():
            self.set_visual(screen.get_rgba_visual())
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "island")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        anchor = {"top": GtkLayerShell.Edge.TOP, "bottom": GtkLayerShell.Edge.BOTTOM,
                  "left": GtkLayerShell.Edge.LEFT, "right": GtkLayerShell.Edge.RIGHT}[self.edge]
        GtkLayerShell.set_anchor(self, anchor, True)
        GtkLayerShell.set_exclusive_zone(self, self.T)     # windows stay clear of the notch

        # A scrolled window without scrollbars is the notch's clip: its size is animated and
        # its content stays centered, so the notch reveals the content as it grows.
        self.sw = Gtk.ScrolledWindow()
        self.sw.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.EXTERNAL)
        self.sw.set_kinetic_scrolling(False)
        self.sw.set_shadow_type(Gtk.ShadowType.NONE)
        A = Gtk.Align
        halign, valign = {"top": (A.CENTER, A.START), "bottom": (A.CENTER, A.END),
                          "left": (A.START, A.CENTER), "right": (A.END, A.CENTER)}[self.edge]
        self.sw.set_halign(halign)
        self.sw.set_valign(valign)
        # The row (or column on the sides) touches the edge; what drops out goes away from it
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL if self.vertical else Gtk.Orientation.VERTICAL)
        row_last = self.edge in ("bottom", "right")
        row = self.build_row()
        if not row_last:
            content.pack_start(row, False, False, 0)
        self.drop = Gtk.Stack()
        self.drop.set_hhomogeneous(False)
        self.drop.set_vhomogeneous(False)
        self.drop.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.drop.set_transition_duration(200)
        self.drop.add_named(Gtk.Box(), "none")
        self.notif = self.build_notif()
        self.drop.add_named(self.notif, "notif")
        self.panel = self.build_panel()
        self.drop.add_named(self.panel, "panel")
        content.pack_start(self.drop, False, False, 0)
        if row_last:
            content.pack_start(row, False, False, 0)
        self.sw.add(content)
        child = self.sw.get_child()
        if isinstance(child, Gtk.Viewport):
            child.set_shadow_type(Gtk.ShadowType.NONE)
        self.add(self.sw)

        # Surface big enough for the open panel plus the spring's overshoot
        content.show_all()
        pw = self.panel.get_preferred_size()[1]
        if self.vertical:
            col = self.row.get_preferred_size()[1].height + 20 * (self.ws_dots.d + self.ws_dots.gap)
            self.surface_w = self.T + max(self.PANEL_W, pw.width) + 60
            self.surface_h = max(pw.height, col, F * 20) + 2 * self.EAR + 80
        else:
            self.surface_w = max(self.PANEL_W, pw.width) + 2 * self.EAR + 60
            self.surface_h = H + max(pw.height, F * 20) + 50
        self.set_size_request(self.surface_w, self.surface_h)
        self.cur_w, self.cur_h = (float(v) for v in self.target_for("rest"))
        self.apply_size()

        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("destroy", Gtk.main_quit)
        self.sw.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.sw.connect("scroll-event", self.on_scroll)
        self.sw.connect("button-press-event", self.on_press)
        self.sw.connect("size-allocate", self.on_allocate)
        for adj in (self.sw.get_hadjustment(), self.sw.get_vadjustment()):
            adj.connect("changed", lambda *_: self.align_content())
            adj.connect("value-changed", lambda *_: self.align_content())

        self.tick()
        GLib.timeout_add(1000, self.tick)
        self.refresh_ws()
        for target in (self.watch_hypr, self.watch_media, self.watch_notifications):
            threading.Thread(target=target, daemon=True).start()
        # SwayNC may start after the island at login: pause its popups now and again later
        for delay in (0, 3000, 10000):
            GLib.timeout_add(delay, self.inhibit_popups)

    # -------------------------------------------------------------- styling
    def apply_css(self):
        F, H = self.F, self.H
        acc = self.palette["accent"]
        ink = ink_for(acc)
        css = f"""
        * {{ font-family: "JetBrainsMono Nerd Font", monospace; font-size: {F}px; color: #f2f2f2;
             outline-style: none; outline-width: 0; text-shadow: none; -gtk-icon-shadow: none; }}
        window, scrolledwindow, viewport {{ background: transparent; border: none; box-shadow: none; }}
        scrolledwindow undershoot, scrolledwindow overshoot {{ background: none; }}
        button {{ background: none; border: none; box-shadow: none; padding: 0; margin: 0;
                  min-height: 0; min-width: 0; border-radius: 0; }}
        .row {{ padding: {f"{self.PAD}px 0" if self.vertical else f"0 {self.PAD}px"}; }}
        .clock {{ font-weight: 800; }}
        .dim {{ color: rgba(255,255,255,0.55); }}
        .bat {{ font-weight: 700; }}
        .card {{ background: rgba(255,255,255,0.08); border-radius: {round(F * 1.2)}px; padding: {round(F * 0.85)}px; }}
        .title {{ font-weight: 700; }}
        .head {{ font-size: {F - 2}px; font-weight: 700; color: rgba(255,255,255,0.5); letter-spacing: 1px; }}
        .round {{ background: rgba(255,255,255,0.12); border-radius: 99px;
                  min-width: {round(F * 2.4)}px; min-height: {round(F * 2.4)}px; }}
        .round:hover {{ background: rgba(255,255,255,0.22); }}
        .play {{ background: #ffffff; }}
        .play label {{ color: #000000; }}
        .play:hover {{ background: rgba(255,255,255,0.85); }}
        .chip {{ background: rgba(255,255,255,0.10); border-radius: 99px; padding: {round(F * 0.4)}px {round(F * 0.6)}px; }}
        .chip:hover {{ background: rgba(255,255,255,0.18); }}
        .chip.on {{ background: {acc}; }}
        .chip.on label {{ color: {ink}; }}
        .link label {{ color: rgba(255,255,255,0.65); }}
        .link:hover label {{ color: #ffffff; }}
        scale trough {{ background: rgba(255,255,255,0.18); border-radius: 99px; min-height: 5px; border: none; }}
        scale highlight {{ background: #ffffff; border-radius: 99px; border: none; }}
        scale slider {{ background: #ffffff; border-radius: 99px; min-width: 12px; min-height: 12px;
                        border: none; box-shadow: none; }}
        .notif-title {{ font-weight: 700; }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        if self.css_provider:
            Gtk.StyleContext.remove_provider_for_screen(screen, self.css_provider)
        Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.css_provider = provider

    def reload_colors_if_changed(self):
        try:
            mtime = COLORS.stat().st_mtime
        except OSError:
            return
        if mtime != self.colors_mtime:
            self.colors_mtime = mtime
            self.palette = load_palette()
            self.apply_css()
            if hasattr(self, "ws_dots"):
                self.ws_dots.accent = hex_rgb(self.palette["accent"])
                self.ws_dots.queue_draw()
            self.queue_draw()

    # -------------------------------------------------------------- building
    def build_row(self):
        F, V = self.F, self.vertical
        O = Gtk.Orientation.VERTICAL if V else Gtk.Orientation.HORIZONTAL
        row = cls(Gtk.Box(orientation=O, spacing=round(F * 0.8) if V else 0), "row")
        if V:
            row.set_size_request(self.T, -1)
        else:
            row.set_size_request(-1, self.H)

        self.ws_dots = WsDots(max(6, round(self.H * 0.24)), lambda i: hypr(f"dispatch workspace {i}"), V)
        row.pack_start(self.ws_dots, False, False, 0)
        self.row = row

        self.mid = Gtk.Stack()
        self.mid.set_hhomogeneous(True)
        self.mid.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.mid.set_transition_duration(160)
        clock = Gtk.Box(orientation=O, spacing=round(F * 0.6))
        clock.set_halign(Gtk.Align.CENTER)
        self.clock_l = label("", "clock")
        self.clock_l.set_justify(Gtk.Justification.CENTER)
        self.date_l = label("", "dim")
        if V:                                   # no room for the date on a side notch
            self.date_l.set_no_show_all(True)
        clock.pack_start(self.clock_l, False, False, 0)
        clock.pack_start(self.date_l, False, False, 0)
        self.mid.add_named(clock, "clock")
        level = Gtk.Box(orientation=O, spacing=round(F * 0.6))
        level.set_halign(Gtk.Align.CENTER)
        self.lv_icon = label("")
        self.lv_bar = Gtk.DrawingArea()
        if V:
            self.lv_bar.set_size_request(round(F * 0.45), round(F * 6))
        else:
            self.lv_bar.set_size_request(round(F * 7), round(F * 0.45))
        self.lv_bar.set_valign(Gtk.Align.CENTER)
        self.lv_bar.set_halign(Gtk.Align.CENTER)
        self.lv_value = 0.0
        self.lv_bar.connect("draw", self.draw_level)
        self.lv_text = label("", "bat")
        self.lv_text.set_width_chars(4)
        self.lv_text.set_justify(Gtk.Justification.CENTER)
        level.pack_start(self.lv_icon, False, False, 0)
        level.pack_start(self.lv_bar, False, False, 0)
        level.pack_start(self.lv_text, False, False, 0)
        self.mid.add_named(level, "level")
        row.set_center_widget(self.mid)

        right = Gtk.Box(orientation=O, spacing=round(F * 0.6))
        self.mini = Gtk.Box(orientation=O, spacing=round(F * 0.4))
        self.mini.set_halign(Gtk.Align.CENTER)
        self.mini_art = RoundImage(round(F * 1.25), round(F * 1.25), radius=4)
        self.eq = Gtk.DrawingArea()
        self.eq.set_size_request(round(F * 1.1), round(F * 0.95))
        self.eq.set_valign(Gtk.Align.CENTER)
        self.eq.connect("draw", self.draw_eq)
        self.mini.pack_start(self.mini_art, False, False, 0)
        self.mini.pack_start(self.eq, False, False, 0)
        self.mini.set_no_show_all(True)            # shown only while something plays
        self.mini_art.show()
        self.eq.show()
        self.bat_l = label("", "bat")
        self.bat_l.set_justify(Gtk.Justification.CENTER)
        right.pack_start(self.mini, False, False, 0)
        right.pack_start(self.bat_l, False, False, 0)
        row.pack_end(right, False, False, 0)
        return row

    def drop_margins(self, w):
        """Padding around what drops out of the notch; small on the side that meets the row."""
        small, P = round(self.F * 0.3), self.PAD
        w.set_margin_top(small if self.edge == "top" else P)
        w.set_margin_bottom(small if self.edge == "bottom" else P)
        w.set_margin_start(small if self.edge == "left" else P)
        w.set_margin_end(small if self.edge == "right" else P)

    def build_notif(self):
        F = self.F
        ev = Gtk.EventBox()
        ev.set_visible_window(False)
        ev.set_above_child(True)                # clicks on the avatar count too
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=round(F * 0.8))
        box.set_size_request(self.NOTIF_W - 2 * self.PAD, -1)
        self.drop_margins(box)
        self.n_avatar = RoundImage(round(F * 2.6), round(F * 2.6))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_valign(Gtk.Align.CENTER)
        self.n_title = label("", "notif-title", xalign=0)
        self.n_body = label("", "dim", xalign=0)
        for lab in (self.n_title, self.n_body):
            lab.set_ellipsize(3)
            lab.set_max_width_chars(40)
        text.pack_start(self.n_title, False, False, 0)
        text.pack_start(self.n_body, False, False, 0)
        box.pack_start(self.n_avatar, False, False, 0)
        box.pack_start(text, True, True, 0)
        ev.add(box)
        ev.connect("button-press-event", lambda *_: self.open_notifications())
        return ev

    def round_button(self, text, action, extra=None):
        b = flat_button(text, "round")
        if extra:
            cls(b, extra)
        b.connect("clicked", lambda *_: action())
        return b

    def build_panel(self):
        F, P = self.F, self.PAD
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=round(F * 0.8))
        panel.set_size_request(self.PANEL_W - 2 * P, -1)
        self.drop_margins(panel)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=round(F * 0.8), homogeneous=True)
        top.pack_start(self.build_music(), True, True, 0)
        top.pack_start(self.build_controls(), True, True, 0)
        panel.pack_start(top, False, False, 0)
        panel.pack_start(self.build_walls(), False, False, 0)
        return panel

    def build_music(self):
        F = self.F
        card = cls(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=round(F * 0.6)), "card")
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=round(F * 0.8))
        self.m_art = RoundImage(round(F * 4.4), round(F * 4.4), radius=round(F * 0.8))
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_valign(Gtk.Align.CENTER)
        self.m_title = label("Nothing playing", "title", xalign=0)
        self.m_artist = label("", "dim", xalign=0)
        for lab in (self.m_title, self.m_artist):
            lab.set_ellipsize(3)
            lab.set_max_width_chars(16)
        info.pack_start(self.m_title, False, False, 0)
        info.pack_start(self.m_artist, False, False, 0)
        top.pack_start(self.m_art, False, False, 0)
        top.pack_start(info, True, True, 0)
        card.pack_start(top, False, False, 0)

        self.m_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.m_scale.set_draw_value(False)
        self.m_scale.set_can_focus(False)
        self.m_scale.connect("button-press-event", lambda *_: self.hold.__setitem__("seek", time.time() + 30) or False)
        self.m_scale.connect("button-release-event", self.on_seek)
        card.pack_start(self.m_scale, False, False, 0)

        ctl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=round(F * 1.4))
        ctl.set_halign(Gtk.Align.CENTER)
        ctl.pack_start(self.round_button(ICON["prev"], lambda: self.media_cmd("previous")), False, False, 0)
        self.play_btn = self.round_button(ICON["play"], lambda: self.media_cmd("play-pause"), "play")
        ctl.pack_start(self.play_btn, False, False, 0)
        ctl.pack_start(self.round_button(ICON["next"], lambda: self.media_cmd("next")), False, False, 0)
        card.pack_start(ctl, False, False, 0)
        return card

    def build_controls(self):
        F = self.F
        S = str(SCRIPTS)
        card = cls(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=round(F * 0.5)), "card")

        def slider(icon, key, setter):
            r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=round(F * 0.6))
            r.pack_start(label(icon), False, False, 0)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            scale.set_draw_value(False)
            scale.set_can_focus(False)

            def changed(s):
                if getattr(s, "_programmatic", False):
                    return
                self.hold[key] = time.time() + 1.2
                setter(int(s.get_value()))
            scale.connect("value-changed", changed)
            r.pack_start(scale, True, True, 0)
            card.pack_start(r, False, False, 0)
            return scale

        self.vol_scale = slider(ICON["volume"], "volume",
                                lambda v: spawn(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{v}%"]))
        self.bri_scale = None
        if qp.BACKLIGHT:
            self.bri_scale = slider(ICON["brightness"], "brightness",
                                    lambda v: spawn(["brightnessctl", "-q", "set", f"{max(v, 1)}%"]))

        grid = Gtk.Grid(column_spacing=round(F * 0.4), row_spacing=round(F * 0.4), column_homogeneous=True)
        grid.set_margin_top(round(F * 0.3))

        def chip(icon, name, action, right=None):
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=round(F * 0.35))
            box.set_halign(Gtk.Align.CENTER)
            box.pack_start(label(icon), False, False, 0)
            box.pack_start(label(name), False, False, 0)
            b = flat_button(box, "chip")
            b.connect("clicked", lambda *_: action())
            if right:
                b.connect("button-press-event", lambda _w, e: (right(), True)[1] if e.button == 3 else False)
            return b

        self.chips = {
            "wifi": chip(ICON["wifi"], "Wi-Fi", self.toggle_wifi, lambda: self.close_then(f"{S}/wifi-menu.sh")),
            "bt": chip(ICON["bt"], "BT", lambda: self.act(f"{S}/toggle-bluetooth.sh"),
                       lambda: self.close_then(f"{S}/bluetooth-menu.sh")),
            "night": chip(ICON["night"], "Night", lambda: self.act(f"{S}/nightlight.sh toggle")),
            "dnd": chip(ICON["silent"], "Silent", lambda: self.act("swaync-client -d -sw")),
            "power": chip(ICON["power"], "Power", lambda: self.close_then(f"{S}/snmenu-toggle.sh")),
            "settings": chip(ICON["settings"], "Settings", lambda: self.close_then(f"python3 {S}/settings.py")),
        }
        for i, b in enumerate(self.chips.values()):
            grid.attach(b, i % 3, i // 3, 1, 1)
        card.pack_start(grid, False, False, 0)
        return card

    def build_walls(self):
        F = self.F
        card = cls(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=round(F * 0.6)), "card")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.pack_start(label("WALLPAPER", "head", xalign=0), True, True, 0)
        more = flat_button("All  \U000f0142", "link")
        more.connect("clicked", lambda *_: self.close_then(f"{SCRIPTS}/rofi-wallpaper.sh"))
        head.pack_end(more, False, False, 0)
        card.pack_start(head, False, False, 0)

        n, gap = 6, round(F * 0.5)
        inner = self.PANEL_W - 2 * self.PAD - 2 * round(F * 0.85)
        tw = (inner - (n - 1) * gap) // n
        th = round(tw * 0.62)
        self.thumb_size = (tw, th)
        strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=gap, homogeneous=True)
        self.thumbs = []
        for i in range(n):
            ev = Gtk.EventBox()
            ev.set_visible_window(False)
            # Above the image: a DrawingArea has its own window, which would swallow the click
            ev.set_above_child(True)
            img = RoundImage(tw, th, radius=round(F * 0.6))
            ev.add(img)
            ev.connect("button-press-event", lambda _w, e, i=i: self.pick_wallpaper(i) if e.button == 1 else False)
            strip.pack_start(ev, True, True, 0)
            self.thumbs.append(img)
        card.pack_start(strip, False, False, 0)
        return card

    # -------------------------------------------------------------- notch shape
    def on_draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        # The shape is drawn as a top notch in (along the edge, away from the edge) coordinates
        # and mapped onto the real edge
        a = self.sw.get_allocation()
        Ws, Hs = self.get_allocated_width(), self.get_allocated_height()
        if self.vertical:
            x, w, h = a.y, a.height, a.width
        else:
            x, w, h = a.x, a.width, a.height
        cr.transform({"top": cairo.Matrix(1, 0, 0, 1, 0, 0), "bottom": cairo.Matrix(1, 0, 0, -1, 0, Hs),
                      "left": cairo.Matrix(0, 1, 1, 0, 0, 0), "right": cairo.Matrix(0, 1, -1, 0, Ws, 0)}[self.edge])
        e = self.EAR
        r = min(h / 2, self.T * 0.5 + max(0, h - self.T) * 0.07, self.F * 2.6)
        cr.move_to(x - e, 0)
        cr.arc(x - e, e, e, -math.pi / 2, 0)                  # left ear (concave)
        cr.line_to(x, h - r)
        cr.arc_negative(x + r, h - r, r, math.pi, math.pi / 2)
        cr.line_to(x + w - r, h)
        cr.arc_negative(x + w - r, h - r, r, math.pi / 2, 0)
        cr.line_to(x + w, e)
        cr.arc(x + w + e, e, e, math.pi, 3 * math.pi / 2)     # right ear
        cr.close_path()
        cr.set_source_rgba(0, 0, 0, 1)
        cr.fill()
        return False

    def on_allocate(self, _w, a):
        self.align_content()
        e = self.EAR
        try:
            if self.vertical:
                rect = cairo.RectangleInt(a.x, max(0, a.y - e), max(1, a.width), a.height + 2 * e)
            else:
                rect = cairo.RectangleInt(max(0, a.x - e), a.y, a.width + 2 * e, max(1, a.height))
            self.input_shape_combine_region(cairo.Region(rect))
        except Exception:
            pass
        self.queue_draw()

    def align_content(self):
        """Content centered along the edge and pinned to the edge, so the notch reveals it
        from the middle as it grows."""
        h, v = self.sw.get_hadjustment(), self.sw.get_vadjustment()
        along, depth = (v, h) if self.vertical else (h, v)
        far = self.edge in ("bottom", "right")
        for adj, k in ((along, 0.5), (depth, 1.0 if far else 0.0)):
            target = max(0.0, (adj.get_upper() - adj.get_page_size()) * k)
            if abs(adj.get_value() - target) > 0.5:
                adj.set_value(target)

    # -------------------------------------------------------------- size animation
    def apply_size(self):
        self.sw.set_size_request(max(1, round(self.cur_w)), max(1, round(self.cur_h)))

    def rest_length(self):
        """Long enough for everything in the row (many workspaces make it longer)."""
        nat = self.row.get_preferred_size()[1]
        return max(self.REST_W, (nat.height if self.vertical else nat.width) + round(self.H * 0.4))

    def target_for(self, mode):
        """Size of the notch (width, height) for a mode."""
        L, T = self.rest_length(), self.T
        if mode in ("rest", "level"):
            return (T, L) if self.vertical else (L, T)
        child = self.notif if mode == "notif" else self.panel
        nat = child.get_preferred_size()[1]
        if self.vertical:
            return T + nat.width, max(L, nat.height)
        return max(L, nat.width), T + nat.height

    def animate_to(self, w, h):
        grow = w * h > self.cur_w * self.cur_h
        self.anim = (self.cur_w, self.cur_h, w, h, time.monotonic(), 0.42 if grow else 0.34, 1.25 if grow else 0.7)
        if self.tick_id is None:
            self.tick_id = self.sw.add_tick_callback(self.on_tick)

    def on_tick(self, _w, _clock):
        if not self.anim:
            self.tick_id = None
            return False
        w0, h0, w1, h1, t0, dur, s = self.anim
        p = min(1.0, (time.monotonic() - t0) / dur)
        k = ease_out_back(p, s)
        self.cur_w = w0 + (w1 - w0) * k
        self.cur_h = h0 + (h1 - h0) * k
        self.apply_size()
        if p >= 1.0:
            self.anim = None
            self.tick_id = None
            return False
        return True

    def update(self, *_):
        now = time.monotonic()
        if self.hover:
            mode = "big"
        elif now < self.notif_until:
            mode = "notif"
        elif now < self.level_until:
            mode = "level"
        else:
            mode = "rest"
        if mode != self.mode:
            was_big = self.mode == "big"
            self.mode = mode
            self.mid.set_visible_child_name("level" if mode == "level" else "clock")
            self.drop.set_visible_child_name({"notif": "notif", "big": "panel"}.get(mode, "none"))
            self.animate_to(*self.target_for(mode))
            if mode == "big":
                self.open_panel()
            elif was_big:
                self.close_panel()
        return False

    # -------------------------------------------------------------- pointer
    def on_enter(self, _w, e):
        if e.detail == Gdk.NotifyType.INFERIOR:
            return False
        if self.collapse_timer:
            GLib.source_remove(self.collapse_timer)
            self.collapse_timer = None
        if not self.hover and not self.expand_timer:
            self.expand_timer = GLib.timeout_add(140, self.do_expand)
        return False

    def on_leave(self, _w, e):
        if e.detail == Gdk.NotifyType.INFERIOR or e.mode == Gdk.CrossingMode.GRAB:
            return False
        if self.expand_timer:
            GLib.source_remove(self.expand_timer)
            self.expand_timer = None
        if self.hover and not self.collapse_timer:
            self.collapse_timer = GLib.timeout_add(350, self.do_collapse)
        return False

    def do_expand(self):
        self.expand_timer = None
        self.hover = True
        self.update()
        return False

    def do_collapse(self):
        self.collapse_timer = None
        self.hover = False
        self.update()
        return False

    def on_press(self, _w, e):
        if not self.hover and e.button == 1:
            self.do_expand()
        return False

    def pointer_in(self, widget, e) -> bool:
        try:
            rx, ry = e.window.get_root_coords(e.x, e.y)
            tx, ty = self.get_window().get_root_coords(0, 0)
            res = widget.translate_coordinates(self, 0, 0)
            wx, wy = res[-2], res[-1]
            a = widget.get_allocation()
            x, y = rx - tx - wx, ry - ty - wy
            return 0 <= x < a.width and 0 <= y < a.height
        except Exception:
            return True

    def on_scroll(self, _w, e):
        if not self.pointer_in(self.row, e):
            return True                 # never scroll the panel itself
        ok, _dx, dy = e.get_scroll_deltas()
        if not ok:
            ok, direction = e.get_scroll_direction()
            dy = {Gdk.ScrollDirection.UP: -1, Gdk.ScrollDirection.DOWN: 1}.get(direction, 0) if ok else 0
        self.scroll_acc += dy
        if abs(self.scroll_acc) >= 1:
            hypr("dispatch workspace " + ("e+1" if self.scroll_acc > 0 else "e-1"))
            self.scroll_acc = 0.0
        return True

    # -------------------------------------------------------------- rest-state content
    def tick(self):
        self.ticks += 1
        self.clock_l.set_text(time.strftime("%H\n%M" if self.vertical else "%H:%M"))
        self.date_l.set_text(time.strftime("%a %d"))
        if self.ticks % 20 == 1:
            bat = read_battery()
            if bat:
                cap, charging = bat
                icon = ICON["charging"] if charging else BATTERY_ICONS[min(10, max(0, round(cap / 10)))]
                self.bat_l.set_text(f"{icon}\n{cap}" if self.vertical else f"{icon} {cap}%")
            self.bat_l.set_visible(bool(bat))
        if self.ticks % 2:
            self.reload_colors_if_changed()
        if self.mode == "big":
            self.tick_progress()
        return True

    def draw_level(self, w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()
        if H > W:                               # side notch: fills from the bottom
            rounded_rect(cr, 0, 0, W, H, W / 2)
            cr.set_source_rgba(1, 1, 1, 0.22)
            cr.fill()
            if self.lv_value > 0:
                fh = max(W, H * min(1.0, self.lv_value))
                rounded_rect(cr, 0, H - fh, W, fh, W / 2)
                cr.set_source_rgba(1, 1, 1, 1)
                cr.fill()
            return False
        rounded_rect(cr, 0, 0, W, H, H / 2)
        cr.set_source_rgba(1, 1, 1, 0.22)
        cr.fill()
        if self.lv_value > 0:
            rounded_rect(cr, 0, 0, max(H, W * min(1.0, self.lv_value)), H, H / 2)
            cr.set_source_rgba(1, 1, 1, 1)
            cr.fill()
        return False

    def draw_eq(self, w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()
        playing = bool(self.media and self.media["playing"])
        t = time.monotonic()
        bw = W / 5
        h = self.palette["accent"].lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        cr.set_source_rgba(r, g, b, 1 if playing else 0.5)
        for i in range(3):
            k = 0.35 + 0.65 * abs(math.sin(t * (5.2 + i * 1.7) + i * 1.3)) if playing else (0.55, 0.9, 0.7)[i]
            bh = max(2, H * k)
            rounded_rect(cr, i * 2 * bw, H - bh, bw, bh, bw / 2)
            cr.fill()
        return False

    def animate_eq(self):
        if self.media and self.media["playing"] and self.mini.get_visible():
            self.eq.queue_draw()
            return True
        self.eq.queue_draw()
        self.eq_timer = None
        return False

    def refresh_ws(self):
        try:
            wss = json.loads(hypr("j/workspaces") or "[]")
            active = json.loads(hypr("j/activeworkspace") or "{}").get("id")
        except ValueError:
            return False
        ids = sorted({1, 2, 3, 4, 5} | {w.get("id", 0) for w in wss if w.get("id", 0) > 0})
        occupied = {w.get("id") for w in wss if w.get("windows", 0) > 0}
        grew = ids != self.ws_ids
        self.ws_ids = ids
        self.ws_dots.set_state(ids, active, occupied)
        if grew and self.mode in ("rest", "level"):      # more or fewer dots: resize the notch
            self.animate_to(*self.target_for(self.mode))
        return False

    # -------------------------------------------------------------- media
    def apply_media(self, m, art):
        old, now = self.media, time.monotonic()
        if m and "position" not in m and old and old.get("title") == m["title"] and "position" in old:
            # playerctl --follow gives no position: keep counting from the last known one
            m["position"] = old["position"] + ((now - self.media_at) if old["playing"] else 0)
        self.media = m
        self.media_at = now
        self.mini.set_visible(bool(m))
        if m:
            self.mini_art.set_visible(bool(self.last_art if art == self.last_art else art))
            if m["playing"] and not self.eq_timer:
                self.eq_timer = GLib.timeout_add(90, self.animate_eq)
            self.eq.queue_draw()
            self.m_title.set_text(m["title"])
            self.m_artist.set_text(m["artist"])
            self.play_btn.get_child().set_text(ICON["pause"] if m["playing"] else ICON["play"])
            if m.get("length", 0) > 0:
                self.m_scale.set_range(0, m["length"])
            if "position" in m and time.time() >= self.hold.get("seek", 0):
                self.m_scale.set_value(m["position"])
        else:
            self.m_title.set_text("Nothing playing")
            self.m_artist.set_text("")
            self.play_btn.get_child().set_text(ICON["play"])
            self.m_scale.set_value(0)
        if art != self.last_art:
            self.last_art = art
            sf = self.get_scale_factor()
            big = load_fill(art, self.m_art.w * sf, self.m_art.h * sf) if art else None
            small = fill_pixbuf(big, self.mini_art.w * sf, self.mini_art.h * sf) if big else None
            self.m_art.set_image(big, "" if big else "♪")
            self.mini_art.set_image(small)
            self.mini_art.set_visible(bool(small) and bool(m))
        return False

    def tick_progress(self):
        m = self.media
        if m and m["playing"] and "position" in m and time.time() >= self.hold.get("seek", 0):
            pos = m["position"] + (time.monotonic() - self.media_at)
            self.m_scale.set_value(min(pos, m.get("length") or pos))

    def media_cmd(self, what):
        spawn(["playerctl", what])
        GLib.timeout_add(250, self.read_slow)

    def on_seek(self, scale, _e):
        spawn(["playerctl", "position", str(int(scale.get_value()))])
        self.hold["seek"] = time.time() + 1.5
        return False

    # -------------------------------------------------------------- panel (while open)
    def open_panel(self):
        self.read_slow()
        self.read_fast()
        self.panel_timers = [GLib.timeout_add(1500, self.read_slow), GLib.timeout_add(300, self.read_fast)]
        self.load_walls()

    def close_panel(self):
        for t in self.panel_timers:
            GLib.source_remove(t)
        self.panel_timers = []

    def read_slow(self):
        if not self.slow_busy:
            self.slow_busy = True

            def work():
                try:
                    st = qp.read_state()
                    m = st.get("media")
                    art = qp.cover_path(m["art"]) if m else None
                except Exception as e:
                    sys.stderr.write(f"island: {e}\n")
                    st, art = None, None
                GLib.idle_add(self.apply_slow, st, art)
            threading.Thread(target=work, daemon=True).start()
        return self.mode == "big"

    def apply_slow(self, st, art):
        self.slow_busy = False
        if not st:
            return False
        self.state.update(st)
        c = self.chips
        set_cls(c["wifi"], "on", st["wifi_on"])
        set_cls(c["bt"], "on", st["bt_on"])
        set_cls(c["night"], "on", bool(st["night"]))
        set_cls(c["dnd"], "on", st["dnd"])
        c["wifi"].set_tooltip_text(st["ssid"] or ("Not connected" if st["wifi_on"] else "Wi-Fi off"))
        c["bt"].set_tooltip_text(st["bt_device"] or ("No device" if st["bt_on"] else "Bluetooth off"))
        self.apply_media(st["media"], art)
        return False

    def read_fast(self):
        if not self.fast_busy:
            self.fast_busy = True

            def work():
                try:
                    st = qp.read_fast()
                except Exception:
                    st = None
                GLib.idle_add(self.apply_fast, st)
            threading.Thread(target=work, daemon=True).start()
        return self.mode == "big"

    def apply_fast(self, st):
        self.fast_busy = False
        if st:
            self.set_scale(self.vol_scale, st["volume"], "volume")
            if self.bri_scale:
                self.set_scale(self.bri_scale, st["brightness"], "brightness")
        return False

    def set_scale(self, scale, value, key):
        if value is None or time.time() < self.hold.get(key, 0):
            return
        if int(scale.get_value()) != value:
            scale._programmatic = True
            scale.set_value(value)
            scale._programmatic = False

    def act(self, cmd):
        spawn(cmd)
        GLib.timeout_add(300, lambda: (self.read_slow(), False)[1])

    def toggle_wifi(self):
        self.act(["nmcli", "radio", "wifi", "off" if self.state.get("wifi_on") else "on"])

    def close_then(self, cmd):
        self.hover = False
        self.update()
        spawn(f"sleep 0.2; {cmd}")

    def open_notifications(self):
        self.notif_until = 0
        self.update()
        spawn("swaync-client -t -sw")
        return True

    # -------------------------------------------------------------- wallpapers
    @staticmethod
    def wallpaper_list():
        exts = (".jpg", ".jpeg", ".png", ".webp")
        try:
            return sorted(str(p) for p in WALLPAPERS.iterdir()
                          if p.is_file() and p.suffix.lower() in exts and p.name != "current.jpg")
        except OSError:
            return []

    def load_walls(self):
        files = self.wallpaper_list()
        current = os.path.realpath(WALLPAPERS / "current.jpg")
        start = files.index(current) if current in files else 0
        shown = [files[(start + i) % len(files)] for i in range(min(len(self.thumbs), len(files)))]
        key = (tuple(shown), current)
        if key == self.walls_key:
            return
        self.walls_key = key
        self.wall_paths = shown
        for i, img in enumerate(self.thumbs):
            img.outline = i < len(shown) and shown[i] == current
            img.set_visible(i < len(shown))
            img.queue_draw()
        sf = self.get_scale_factor()
        tw, th = self.thumb_size[0] * sf, self.thumb_size[1] * sf

        def work():
            THUMBS.mkdir(parents=True, exist_ok=True)
            for i, path in enumerate(shown):
                try:
                    tag = f"{path}:{os.path.getmtime(path)}:{tw}x{th}"
                except OSError:
                    continue
                cache = THUMBS / (hashlib.md5(tag.encode()).hexdigest() + ".png")
                pix = None
                if cache.exists():
                    try:
                        pix = GdkPixbuf.Pixbuf.new_from_file(str(cache))
                    except Exception:
                        pix = None
                if pix is None:
                    pix = load_fill(path, tw, th)
                    if pix:
                        try:
                            pix.savev(str(cache), "png", [], [])
                        except Exception:
                            pass
                if pix:
                    GLib.idle_add(self.set_thumb, i, path, pix)
        threading.Thread(target=work, daemon=True).start()

    def set_thumb(self, i, path, pix):
        if i < len(self.wall_paths) and self.wall_paths[i] == path:
            self.thumbs[i].set_image(pix)
        return False

    def pick_wallpaper(self, i):
        if i >= len(self.wall_paths):
            return True
        path = self.wall_paths[i]
        files = self.wallpaper_list()
        if path in files:
            try:
                (HOME / ".cache" / "wal").mkdir(parents=True, exist_ok=True)
                (HOME / ".cache" / "wal" / "current_index").write_text(f"{files.index(path)}\n")
            except OSError:
                pass
        spawn([str(SCRIPTS / "set-wallpaper.sh"), path, "outer"])
        for k, img in enumerate(self.thumbs):            # move the outline right away
            img.outline = k == i
            img.queue_draw()
        return True

    # -------------------------------------------------------------- notifications and levels
    def on_notify(self, n):
        if n["value"] is not None or n["sync"]:
            self.show_level(n)
        elif not n["dnd"]:
            self.show_notif(n)
        return False

    def show_level(self, n):
        summary, body, value = n["summary"].lower(), n["body"], n["value"]
        if "bright" in summary:
            icon = ICON["brightness"]
        elif "micro" in summary:
            icon = ICON["mic_off"] if "mute" in body.lower() else ICON["mic"]
        elif "volume" in summary or "sound" in summary:
            icon = ICON["muted"] if "mute" in body.lower() else ICON["volume"]
        else:
            icon = ICON["bell"]
        self.lv_icon.set_text(icon)
        if value is None:
            self.lv_bar.hide()
            self.lv_text.set_width_chars(-1)
            self.lv_text.set_text(re.sub(r"\s*[\U000f0000-\U000fffff]\s*", "", body).strip() or n["summary"])
        else:
            self.lv_bar.show()
            self.lv_text.set_width_chars(4)
            self.lv_value = max(0, min(100, value)) / 100
            self.lv_text.set_text("Muted" if "mute" in body.lower() else f"{value}%")
            self.lv_bar.queue_draw()
        self.level_until = time.monotonic() + 1.6
        self.update()
        GLib.timeout_add(1650, self.update)

    def show_notif(self, n):
        app = n["app"] or "Notification"
        title = f"{app} · {n['summary']}" if n["summary"] and n["summary"] != app else app
        self.n_title.set_text(title)
        self.n_body.set_text(n["body"].replace("\n", "  "))
        self.n_body.set_visible(bool(n["body"]))
        size = self.n_avatar.w * self.get_scale_factor()
        pix = None
        for cand in (n["image"], n["icon"], n["desktop"], app.lower()):
            if not cand:
                continue
            try:
                if cand.startswith("file://"):
                    cand = urllib.request.url2pathname(cand[7:])
                if cand.startswith("/"):
                    if os.path.isfile(cand):
                        pix = load_fill(cand, size, size)
                else:
                    theme = Gtk.IconTheme.get_default()
                    if theme.has_icon(cand):
                        pix = theme.load_icon(cand, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except Exception:
                pix = None
            if pix:
                break
        h = self.palette["accent"].lstrip("#")
        color = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)
        self.n_avatar.set_image(pix, (app[:1] or "?").upper(), color)
        dur = 8.0 if n["urgency"] == 2 else 4.5
        self.notif_until = time.monotonic() + dur
        self.update()
        if self.mode == "notif":                          # the text may be taller than before
            self.animate_to(*self.target_for("notif"))
        GLib.timeout_add(int(dur * 1000) + 50, self.update)

    @staticmethod
    def parse_notify(text: str):
        strings = re.findall(r'^\s*string "(.*?)"$', text, re.S | re.M)
        if len(strings) < 4:
            return None

        def hint_str(name):
            m = re.search(r'string "%s"\s*variant\s+string "(.*?)"$' % re.escape(name), text, re.S | re.M)
            return m.group(1) if m else ""
        value = re.search(r'string "value"\s*variant\s+(?:u?int(?:16|32|64)|byte)\s+(\d+)', text)
        urgency = re.search(r'string "urgency"\s*variant\s+(?:byte|u?int32)\s+(\d+)', text)
        body = html.unescape(re.sub(r"<[^>]+>", "", strings[3]))
        return {
            "app": strings[0], "icon": strings[1], "summary": html.unescape(strings[2]), "body": body.strip(),
            "value": int(value.group(1)) if value else None,
            "sync": "x-canonical-private-synchronous" in text,
            "urgency": int(urgency.group(1)) if urgency else 1,
            "image": hint_str("image-path") or hint_str("image_path"),
            "desktop": hint_str("desktop-entry"),
            "dnd": False,
        }

    def watch_notifications(self):
        """Every Notify call on the session bus (the island only reads them; SwayNC still shows
        them in its list)."""
        if not have("dbus-monitor"):
            sys.stderr.write("island: dbus-monitor not found (package dbus-bin): no notifications\n")
            return
        rule = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"
        while True:
            try:
                proc = subprocess.Popen(["dbus-monitor", "--session", rule], stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, errors="replace")
            except OSError:
                return
            self.procs.append(proc)
            buf, inside = [], False
            for line in proc.stdout:
                if line.startswith(("method call", "signal ", "method return", "error ")):
                    inside = "member=Notify" in line
                    buf = []
                    continue
                if not inside:
                    continue
                buf.append(line)
                # The last argument of Notify is the expire timeout, a top-level int32
                if re.match(r"^   int32 -?\d+\s*$", line):
                    inside = False
                    n = self.parse_notify("".join(buf))
                    if n:
                        if n["value"] is None and not n["sync"]:
                            n["dnd"] = run(["swaync-client", "-D"], timeout=1) == "true"
                        GLib.idle_add(self.on_notify, n)
            time.sleep(2)                                 # dbus-monitor exited: start again

    def inhibit_popups(self):
        if have("swaync-client"):
            spawn(["swaync-client", "--inhibitor-add", INHIBITOR])
        return False

    # -------------------------------------------------------------- watchers
    def watch_hypr(self):
        """Workspace changes, straight from Hyprland's event socket."""
        while True:
            path = hypr_socket(".socket2.sock")
            if path:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(path)
                        for line in s.makefile("r", errors="replace"):
                            if line.split(">>", 1)[0] in WS_EVENTS and not self.ws_pending:
                                self.ws_pending = True
                                GLib.idle_add(self._ws_idle)
                except OSError:
                    pass
            time.sleep(2)

    def _ws_idle(self):
        self.ws_pending = False
        self.refresh_ws()
        return False

    def watch_media(self):
        """Now playing, pushed by playerctl as soon as it changes."""
        if not have("playerctl"):
            return
        fmt = "{{status}}\t{{title}}\t{{artist}}\t{{mpris:artUrl}}\t{{mpris:length}}"
        while True:
            try:
                proc = subprocess.Popen(["playerctl", "--follow", "metadata", "--format", fmt],
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
            except OSError:
                return
            self.procs.append(proc)
            for line in proc.stdout:
                f = line.rstrip("\n").split("\t")
                m, art = None, None
                if len(f) == 5 and f[0] in ("Playing", "Paused") and f[1].strip():
                    try:
                        length = int(f[4]) / 1_000_000
                    except ValueError:
                        length = 0.0
                    m = {"playing": f[0] == "Playing", "title": f[1], "artist": f[2], "art": f[3], "length": length}
                    art = qp.cover_path(f[3])
                GLib.idle_add(self.apply_media, m, art)
            time.sleep(2)

    def cleanup(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
        if have("swaync-client"):
            run(["swaync-client", "--inhibitor-remove", INHIBITOR], timeout=1)


def main():
    # One island at a time: a new one replaces the old one
    if PID_FILE.exists():
        try:
            old = int(PID_FILE.read_text().strip())
            if old != os.getpid():
                os.kill(old, signal.SIGTERM)
                time.sleep(0.2)
        except (OSError, ValueError):
            pass
    PID_FILE.write_text(str(os.getpid()))
    win = None
    try:
        win = Island()
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (Gtk.main_quit(), False)[1])
        win.show_all()
        win.mini.set_visible(False)
        Gtk.main()
    finally:
        if win:
            win.cleanup()
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
