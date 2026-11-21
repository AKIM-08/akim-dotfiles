#!/usr/bin/env python3
"""desktop-extras.py - small desktop touches, in one light background program (started by Hyprland).

    volume & brightness   the volume, brightness and mic keys show a small pill with a level bar
                          near the bottom instead of a notification (the island does its own)
    desktop widgets       a big clock, the date, the song playing and a calendar drawn on the
                          wallpaper, under the windows
    window overview       Alt + Tab: every window as a picture (overview.py, shown from here so
                          it opens at once); a picture of each workspace is kept for it
    screens               a screen plugged in or out gets its place back (screens.py restore)
    charging              plugging the charger in shows a ring filling to the battery level;
                          a red one warns when the battery gets low (click it for Power saver)

Each can be turned on or off in Settings -> Appearance -> Desktop (stored in
~/.config/hypr/desktop-extras.json, read again when it changes). Colors follow the wallpaper.
"""

import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk   # noqa: E402
import cairo                                                # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell                # noqa: E402
except (ImportError, ValueError):
    sys.stderr.write("desktop-extras: gtk-layer-shell is missing\n")
    sys.exit(0)

HOME = Path.home()
SCRIPTS = Path(__file__).resolve().parent
CONFIG = HOME / ".config" / "hypr" / "desktop-extras.json"
COLORS = HOME / ".cache" / "wal" / "colors.json"
PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "desktop-extras.pid"
DEFAULTS = {"osd": True, "charging": True, "clock": False, "song": False, "calendar": False}
OSD_FIFO = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "desktop-osd.fifo"
OSD_ON = OSD_FIFO.with_suffix(".on")        # exists while the pop-up is switched on
LOW, CRITICAL = 15, 5


# ------------------------------------------------------------------------------ helpers
def run(cmd, timeout=3):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def read_config():
    try:
        saved = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    if "widgets" in saved:                  # older single switch for all the widgets
        for k in ("clock", "song", "calendar"):
            saved.setdefault(k, bool(saved["widgets"]))
    return {**DEFAULTS, **saved}


def palette():
    c = {"bg": "#141824", "fg": "#eef1f7", "accent": "#7aa2f7"}
    try:
        d = json.loads(COLORS.read_text(encoding="utf-8"))
        c = {"bg": d["special"]["background"], "fg": d["special"]["foreground"], "accent": d["colors"]["color1"]}
    except (OSError, ValueError, KeyError):
        pass
    return c


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgba(h, a):
    r, g, b = (round(v * 255) for v in rgb(h))
    return f"rgba({r},{g},{b},{a})"


def ink(h):
    r, g, b = rgb(h)
    return "#101010" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else "#ffffff"


def battery():
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            return int((bat / "capacity").read_text()), (bat / "status").read_text().strip(), bat.name
        except (OSError, ValueError):
            continue
    return None


def on_ac():
    """True / False when the laptop says whether the charger is plugged in, None if it can't."""
    for ps in Path("/sys/class/power_supply").iterdir() if Path("/sys/class/power_supply").is_dir() else []:
        try:
            if (ps / "type").read_text().strip() == "Mains":
                return (ps / "online").read_text().strip() == "1"
        except OSError:
            continue
    return None


def time_left(bat_name, key):
    out = run(["upower", "-i", f"/org/freedesktop/UPower/devices/battery_{bat_name}"])
    m = re.search(rf"time to {key}:\s*(.+)", out)
    return m.group(1).strip() if m else ""


def layer(win, namespace, layer_kind, anchors=(), keyboard=False, exclusive=-1):
    win.set_app_paintable(True)
    if win.get_screen().get_rgba_visual():
        win.set_visual(win.get_screen().get_rgba_visual())
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_namespace(win, namespace)
    GtkLayerShell.set_layer(win, layer_kind)
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
    GtkLayerShell.set_exclusive_zone(win, exclusive)
    for e in anchors:
        GtkLayerShell.set_anchor(win, e, True)


def die_with_parent():
    """For watcher subprocesses: the kernel stops them when this program ends, however it ends."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, 15)   # PR_SET_PDEATHSIG, SIGTERM
    except (OSError, AttributeError):
        pass


def click_through(win, keep=None):
    """No input at all, or only inside `keep` (a widget)."""
    if keep is None:
        win.input_shape_combine_region(cairo.Region())
        return
    a = keep.get_allocation()
    win.input_shape_combine_region(cairo.Region(cairo.RectangleInt(a.x, a.y, a.width, a.height)))


# ------------------------------------------------------------------------------ a fading card
class Flash(Gtk.Window):
    """A card in the middle of the screen that fades in, stays, and fades out."""

    def __init__(self, extras):
        super().__init__()
        self.extras = extras
        layer(self, "desktop-extras", GtkLayerShell.Layer.OVERLAY)
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.card.get_style_context().add_class("flash")
        self.ev = Gtk.EventBox()
        self.ev.set_visible_window(False)
        self.ev.add(self.card)
        self.ev.connect("button-press-event", self.on_click)
        self.add(self.ev)
        self.on_click_action = None
        self.subtitle = None
        self.hide_at = 0
        self.t0 = 0
        self.tick = None
        self.connect("size-allocate", lambda *_: click_through(self, self.ev if self.on_click_action else None))

    def show_for(self, seconds, clickable=None):
        self.on_click_action = clickable
        self.t0 = time.monotonic()
        self.hide_at = self.t0 + seconds
        self.card.set_opacity(0)
        self.show_all()
        if self.tick is None:
            self.tick = self.add_tick_callback(self.fade)

    def fade(self, *_):
        now = time.monotonic()
        a = min(1.0, (now - self.t0) / 0.15)
        if now > self.hide_at:
            a = max(0.0, 1 - (now - self.hide_at) / 0.3)
        self.card.set_opacity(a)
        self.card.queue_draw()
        if now > self.hide_at + 0.3:
            self.hide()
            self.tick = None
            return False
        return True

    def clear(self):
        for c in self.card.get_children():
            self.card.remove(c)

    def on_click(self, *_):
        if self.on_click_action:
            self.on_click_action()
            self.hide_at = time.monotonic()
        return True


# ------------------------------------------------------------------------------ desktop widgets
class Widgets(Gtk.Window):
    """Clock, date, song and calendar on the desktop: under the windows (bottom layer)."""

    def __init__(self, extras):
        super().__init__()
        self.extras = extras
        E = GtkLayerShell.Edge
        layer(self, "desktop-widgets", GtkLayerShell.Layer.BOTTOM, (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT), exclusive=0)
        grid = Gtk.Overlay()
        grid.add(Gtk.Box())
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.set_halign(Gtk.Align.START)
        left.set_valign(Gtk.Align.END)
        left.set_margin_start(70)
        left.set_margin_bottom(80)
        self.clock = Gtk.Label(xalign=0)
        self.clock.get_style_context().add_class("w-clock")
        self.date = Gtk.Label(xalign=0)
        self.date.get_style_context().add_class("w-date")
        left.pack_start(self.clock, False, False, 0)
        left.pack_start(self.date, False, False, 0)
        self.clock.set_no_show_all(True)
        self.date.set_no_show_all(True)
        self.song = Gtk.Box(spacing=12)
        self.song.get_style_context().add_class("w-card")
        self.song.set_halign(Gtk.Align.START)
        self.song.set_margin_top(14)
        self.cover = Gtk.Image()
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        texts.set_valign(Gtk.Align.CENTER)
        self.title = Gtk.Label(xalign=0)
        self.title.get_style_context().add_class("w-title")
        self.title.set_ellipsize(3)
        self.title.set_max_width_chars(30)
        self.artist = Gtk.Label(xalign=0)
        self.artist.get_style_context().add_class("w-sub")
        texts.pack_start(self.title, False, False, 0)
        texts.pack_start(self.artist, False, False, 0)
        self.song.pack_start(self.cover, False, False, 0)
        self.song.pack_start(texts, True, True, 0)
        self.song.set_no_show_all(True)
        self.cover.show()
        texts.show_all()
        left.pack_start(self.song, False, False, 0)
        grid.add_overlay(left)
        self.cal = Gtk.Label()
        self.cal.get_style_context().add_class("w-card")
        self.cal.get_style_context().add_class("w-cal")
        self.cal.set_halign(Gtk.Align.END)
        self.cal.set_valign(Gtk.Align.END)
        self.cal.set_margin_end(70)
        self.cal.set_margin_bottom(80)
        self.cal.set_no_show_all(True)
        grid.add_overlay(self.cal)
        self.add(grid)
        self.connect("size-allocate", lambda *_: click_through(self))
        self.cal_day = None
        self.song_on = False
        self.last_song = None
        self.alive = True
        self.proc = None
        self.connect("destroy", self.on_destroy)
        self.tick()
        GLib.timeout_add(1000, self.tick)
        threading.Thread(target=self.watch_song, daemon=True).start()

    def show_parts(self, cfg):
        """Which widgets are switched on in Settings."""
        for w in (self.clock, self.date):
            w.set_visible(cfg["clock"])
        self.cal.set_visible(cfg["calendar"])
        self.song_on = cfg["song"]
        self.set_song(self.last_song)

    def on_destroy(self, *_):
        self.alive = False
        if self.proc:
            self.proc.terminate()

    def tick(self):
        if not self.alive:
            return False
        self.clock.set_text(time.strftime("%H:%M"))
        self.date.set_text(time.strftime("%A %-d %B"))
        if self.cal_day != time.strftime("%j"):
            self.cal_day = time.strftime("%j")
            self.calendar()
        return True

    def calendar(self):
        import calendar as cal
        today = time.localtime()
        acc = self.extras.pal["accent"]
        lines = [f'<b><span foreground="{acc}">{time.strftime("%B %Y"):^20}</span></b>', "Mo Tu We Th Fr Sa Su"]
        for week in cal.Calendar(0).monthdayscalendar(today.tm_year, today.tm_mon):
            cells = []
            for d in week:
                if d == 0:
                    cells.append("  ")
                elif d == today.tm_mday:
                    cells.append(f'<span background="{acc}" foreground="{ink(acc)}"><b>{d:2}</b></span>')
                else:
                    cells.append(f"{d:2}")
            lines.append(" ".join(cells))
        self.cal.set_markup("\n".join(lines))

    def watch_song(self):
        fmt = "{{status}}\t{{title}}\t{{artist}}\t{{mpris:artUrl}}"
        while self.alive:
            try:
                self.proc = subprocess.Popen(["playerctl", "--follow", "metadata", "--format", fmt],
                                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace",
                                             preexec_fn=die_with_parent)
            except OSError:
                return
            for line in self.proc.stdout:
                f = line.rstrip("\n").split("\t")
                if self.alive:
                    GLib.idle_add(self.set_song, f if len(f) == 4 and f[0] in ("Playing", "Paused") and f[1] else None)
            time.sleep(3)

    def set_song(self, f):
        if not self.alive:
            return False
        self.last_song = f
        if not f or not self.song_on:
            self.song.hide()
            return False
        self.title.set_text(f[1])
        self.artist.set_text(f[2])
        pix = None
        url = f[3]
        if url.startswith("file://"):
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(url[7:], 48, 48, True)
            except Exception:
                pix = None
        if pix:
            self.cover.set_from_pixbuf(pix)
        else:
            self.cover.set_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
        self.song.show()
        return False


# ------------------------------------------------------------------------------ volume & brightness
class Osd(Gtk.Window):
    """A pill near the bottom: icon, level bar, percent. Updates in place, fades after a second."""

    ICONS = {"volume": "\U000f057e", "volume-low": "\U000f057f", "volume-mid": "\U000f0580",
             "muted": "\U000f075f", "brightness": "\U000f00e0", "mic": "\U000f036c", "mic-off": "\U000f036d"}

    def __init__(self, extras):
        super().__init__()
        self.extras = extras
        layer(self, "desktop-osd", GtkLayerShell.Layer.OVERLAY, (GtkLayerShell.Edge.BOTTOM,))
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 90)
        self.pill = Gtk.Box(spacing=14)
        self.pill.get_style_context().add_class("osd")
        self.icon = Gtk.Label()
        self.icon.get_style_context().add_class("osd-icon")
        self.bar = Gtk.DrawingArea()
        self.bar.set_size_request(190, 8)
        self.bar.set_valign(Gtk.Align.CENTER)
        self.bar.connect("draw", self.draw_bar)
        self.value = Gtk.Label(xalign=1)
        self.value.set_width_chars(5)
        self.value.get_style_context().add_class("osd-value")
        for w in (self.icon, self.bar, self.value):
            self.pill.pack_start(w, False, False, 0)
        self.add(self.pill)
        self.connect("size-allocate", lambda *_: click_through(self))
        self.level = self.shown = 0.0
        self.muted = False
        self.hide_at = self.t0 = 0
        self.tick = None

    def draw_bar(self, w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()

        def pill(width):
            r = H / 2
            cr.new_sub_path()
            cr.arc(r, r, r, math.pi / 2, 3 * math.pi / 2)
            cr.arc(max(r, width - r), r, r, -math.pi / 2, math.pi / 2)
            cr.close_path()
        fg = rgb(self.extras.pal["fg"])
        cr.set_source_rgba(*fg, 0.16)
        pill(W)
        cr.fill()
        if self.shown > 0.005:
            if self.muted:
                cr.set_source_rgba(*fg, 0.45)
            else:
                cr.set_source_rgba(*rgb(self.extras.pal["accent"]), 1)
            pill(max(H, W * min(1.0, self.shown)))
            cr.fill()
        return False

    def show_level(self, kind, value, muted=False):
        if kind == "volume":
            icon = "muted" if muted else ("volume-low" if value < 34 else "volume-mid" if value < 67 else "volume")
            text = "Muted" if muted else f"{value}%"
        elif kind == "mic":
            icon, value, text = ("mic-off", 0, "Off") if muted else ("mic", 100, "On")
        else:
            icon, text = "brightness", f"{value}%"
        self.icon.set_text(self.ICONS[icon])
        self.value.set_text(text)
        self.muted = muted
        self.level = max(0, value) / 100
        now = time.monotonic()
        if not self.get_visible():
            self.t0 = now
            self.shown = self.level
            self.pill.set_opacity(0)
            self.show_all()
        self.hide_at = now + 1.1
        if self.tick is None:
            self.tick = self.add_tick_callback(self.animate)

    def animate(self, *_):
        now = time.monotonic()
        self.shown += (self.level - self.shown) * 0.3
        a = min(1.0, (now - self.t0) / 0.12)
        if now > self.hide_at:
            a = max(0.0, 1 - (now - self.hide_at) / 0.3)
        self.pill.set_opacity(a)
        self.bar.queue_draw()
        if now > self.hide_at + 0.3:
            self.hide()
            self.tick = None
            return False
        return True


def osd_reader(on_line):
    """Lines written to the FIFO by volume-control.sh / brightness-control.sh."""
    try:
        if OSD_FIFO.exists() and not OSD_FIFO.is_fifo():
            OSD_FIFO.unlink()
        if not OSD_FIFO.exists():
            os.mkfifo(OSD_FIFO, 0o600)
        fd = os.open(OSD_FIFO, os.O_RDWR)          # read+write: never sees end-of-file
    except OSError as e:
        sys.stderr.write(f"desktop-extras: no pop-up ({e})\n")
        return
    with os.fdopen(fd, "r", errors="replace") as f:
        for line in f:
            GLib.idle_add(on_line, line.split())


# ------------------------------------------------------------------------------ the program
class Extras:
    def __init__(self):
        self.cfg = read_config()
        self.cfg_mtime = None
        self.pal = palette()
        self.pal_mtime = None
        self.provider = None
        self.css()
        self.flash = Flash(self)
        self.osd = Osd(self)
        self.widgets = None
        self.last_bat = battery()
        self.last_ac = on_ac()
        self.warned = set()
        self.apply_config()
        GLib.timeout_add(2000, self.poll)
        GLib.timeout_add(700, self.check_battery)
        threading.Thread(target=osd_reader, args=(self.on_osd,), daemon=True).start()
        threading.Thread(target=self.watch_hyprland, daemon=True).start()
        # screens: put a connected screen where it was chosen (e.g. "only the other one")
        subprocess.Popen(["python3", str(SCRIPTS / "screens.py"), "restore"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.overview = None
        self.snap_timer = 0

    def css(self):
        a, b, f = self.pal["accent"], self.pal["bg"], self.pal["fg"]
        css = f"""
        * {{ font-family: "Inter", "JetBrainsMono Nerd Font", sans-serif; color: {f}; text-shadow: none; }}
        window {{ background: transparent; }}
        .flash {{ background: {rgba(b, .86)}; border: 1px solid {rgba(f, .14)}; border-radius: 26px; padding: 22px 34px; }}
        .osd {{ background: {rgba(b, .88)}; border: 1px solid {rgba(f, .12)}; border-radius: 999px; padding: 12px 22px; }}
        .osd-icon {{ font-family: "JetBrainsMono Nerd Font"; font-size: 20px; color: {a}; }}
        .osd-value {{ font-weight: 700; font-size: 14px; }}
        .big {{ font-size: 20px; font-weight: 800; }}
        .sub {{ font-size: 13px; color: {rgba(f, .65)}; }}
        .low .big {{ color: #ff6b6b; }}
        .w-clock {{ font-size: 92px; font-weight: 800; letter-spacing: -2px; color: {f};
                    text-shadow: 0 2px 14px rgba(0,0,0,0.45); }}
        .w-date {{ font-size: 24px; font-weight: 700; color: {a}; text-shadow: 0 2px 10px rgba(0,0,0,0.45); }}
        .w-card {{ background: {rgba(b, .55)}; border-radius: 16px; padding: 10px 14px; }}
        .w-title {{ font-weight: 700; font-size: 14px; }}
        .w-sub {{ color: {rgba(f, .65)}; font-size: 12px; }}
        .w-cal {{ font-family: "JetBrainsMono Nerd Font", monospace; font-size: 14px; padding: 14px 18px; }}
        """
        prov = Gtk.CssProvider()
        prov.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        if self.provider:
            Gtk.StyleContext.remove_provider_for_screen(screen, self.provider)
        Gtk.StyleContext.add_provider_for_screen(screen, prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.provider = prov

    def apply_config(self):
        want = self.cfg["clock"] or self.cfg["song"] or self.cfg["calendar"]
        if want and self.widgets is None:
            self.widgets = Widgets(self)
            self.widgets.show_all()
        elif not want and self.widgets is not None:
            self.widgets.destroy()
            self.widgets = None
        if self.widgets:
            self.widgets.show_parts(self.cfg)
        # The volume / brightness scripts only send here while this file exists
        try:
            if self.cfg["osd"]:
                OSD_ON.touch()
            else:
                OSD_ON.unlink(missing_ok=True)
        except OSError:
            pass

    def on_osd(self, words):
        """volume <0-150> <0|1 muted> · brightness <0-100> · mic <0|1 muted>"""
        try:
            kind = words[0]
            if kind == "volume":
                self.osd.show_level("volume", int(words[1]), words[2:3] == ["1"])
            elif kind == "brightness":
                self.osd.show_level("brightness", int(words[1]))
            elif kind == "mic":
                self.osd.show_level("mic", 0, words[1:2] == ["1"])
            elif kind == "test-charging":
                bat = battery() or (80, "Charging", "BAT0")
                self.show_ring(bat[0], False, f"{bat[0]}% · charging", "Preview")
            elif kind == "test-low":
                self.show_ring(12, True, "Battery 12%", "Preview · click for Power saver")
            elif kind in ("overview", "overview-back", "overview-release"):
                self.on_overview(kind)
        except (IndexError, ValueError):
            pass
        return False

    # -------------------------------------------------------------- overview + screens
    def on_overview(self, kind):
        import importlib
        import overview
        # overview.py changed since it was loaded (an update): use the new version
        try:
            mtime = Path(overview.__file__).stat().st_mtime
        except OSError:
            mtime = 0
        if self.overview is not None and mtime != getattr(self, "overview_mtime", mtime) \
                and not self.overview.get_visible():
            self.overview.destroy()
            self.overview = None
            overview = importlib.reload(overview)
        self.overview_mtime = mtime
        if self.overview is None:
            self.overview = overview.Overview()
        ov = self.overview
        if kind == "overview":
            ov.open()
        elif kind == "overview-back" and ov.get_visible():
            ov.move(-1)
        elif kind == "overview-back":
            ov.open()
        elif kind == "overview-release" and ov.get_visible() and not ov.sticky \
                and time.monotonic() - ov.opened < 2.5:
            ov.jump()                       # Alt let go before the overview had the keyboard

    def watch_hyprland(self):
        """Hyprland events: workspace pictures for the overview, screens plugged in or out."""
        import socket
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        path = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "hypr" / sig / ".socket2.sock"
        while True:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(str(path))
                    for line in s.makefile("r", errors="replace"):
                        ev, _, data = line.strip().partition(">>")
                        if ev == "workspacev2":
                            ident = data.split(",", 1)[0]
                            if ident.lstrip("-").isdigit() and int(ident) > 0:
                                GLib.idle_add(self.schedule_snapshot, int(ident))
                        elif ev in ("monitoraddedv2", "monitorremoved"):
                            subprocess.Popen(["python3", str(SCRIPTS / "screens.py"), "restore"],
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
            time.sleep(2)

    def schedule_snapshot(self, ws):
        """A second after arriving on a workspace (windows settled), keep a small picture of it."""
        if self.snap_timer:
            GLib.source_remove(self.snap_timer)

        def take():
            self.snap_timer = 0
            if self.overview is not None and self.overview.get_visible():
                return False
            import overview
            threading.Thread(target=overview.snapshot_workspace, args=(ws,), daemon=True).start()
            return False
        self.snap_timer = GLib.timeout_add(1000, take)
        return False

    def poll(self):
        """Every 2 s: settings, palette, battery (all cheap file reads)."""
        try:
            m = CONFIG.stat().st_mtime
        except OSError:
            m = None
        if m != self.cfg_mtime:
            self.cfg_mtime = m
            self.cfg = read_config()
            self.apply_config()
        try:
            m = COLORS.stat().st_mtime
        except OSError:
            m = None
        if m != self.pal_mtime:
            self.pal_mtime = m
            self.pal = palette()
            self.css()
            if self.widgets:
                self.widgets.calendar()
        return True

    # -------------------------------------------------------------- charging / low battery
    def check_battery(self):
        """Every 0.7 s (two small file reads): charger plugged in, or battery getting low."""
        bat = battery()
        ac = on_ac()
        prev_bat, prev_ac = self.last_bat, self.last_ac
        self.last_bat, self.last_ac = bat, ac
        if not bat or not self.cfg["charging"]:
            return True
        cap, status, name = bat
        if ac is not None and prev_ac is not None:
            plugged = ac and not prev_ac                          # the charger reports itself
        else:
            plugged = bool(prev_bat) and prev_bat[1] == "Discharging" and status in ("Charging", "Full", "Not charging")
        if plugged:
            self.warned.clear()
            if status == "Full" or cap >= 99:
                self.show_ring(cap, False, "Fully charged", "")
            else:
                # the time estimate needs a moment after plugging in
                GLib.timeout_add(1500, self.show_charging, name)
                self.show_ring(cap, False, f"{cap}% · charging", "")
        elif status == "Discharging" and not ac:
            for level in (LOW, CRITICAL):
                if cap <= level and level not in self.warned:
                    self.warned.add(level)
                    left = time_left(name, "empty")
                    self.show_ring(cap, True, f"Battery {cap}%", (f"{left} left · " if left else "") + "click for Power saver")
                    break
        return True

    def show_charging(self, name):
        left = time_left(name, "full")
        if left and self.flash.get_visible() and self.flash.subtitle is not None:
            self.flash.subtitle.set_text(f"Full in {left}")
            self.flash.subtitle.show()
        return False

    def show_ring(self, cap, low, title, sub):
        f = self.flash
        f.clear()
        ctx = f.card.get_style_context()
        (ctx.add_class if low else ctx.remove_class)("low")
        area = Gtk.DrawingArea()
        area.set_size_request(150, 150)
        acc = (1.0, 0.42, 0.42) if low else rgb(self.pal["accent"])
        t0 = time.monotonic()

        def draw(w, cr):
            W, H = w.get_allocated_width(), w.get_allocated_height()
            cx, cy, r = W / 2, H / 2, min(W, H) / 2 - 10
            k = min(1.0, (time.monotonic() - t0) / 1.1)
            k = 1 - (1 - k) ** 3
            cr.set_line_width(10)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(1, 1, 1, 0.12)
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.stroke()
            cr.set_source_rgba(*acc, 1)
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * cap / 100 * k)
            cr.stroke()
            # bolt (charging) or exclamation (low)
            cr.set_source_rgba(*acc, 1)
            if low:
                cr.rectangle(cx - 5, cy - 30, 10, 38)
                cr.fill()
                cr.arc(cx, cy + 22, 6, 0, 2 * math.pi)
                cr.fill()
            else:
                pts = [(4, -34), (-18, 4), (-2, 4), (-6, 34), (18, -6), (2, -6)]
                cr.move_to(cx + pts[0][0], cy + pts[0][1])
                for x, y in pts[1:]:
                    cr.line_to(cx + x, cy + y)
                cr.close_path()
                cr.fill()
            return False
        area.connect("draw", draw)
        area.add_tick_callback(lambda *_: (area.queue_draw(), time.monotonic() - t0 < 1.3)[1])
        area.set_halign(Gtk.Align.CENTER)
        f.card.pack_start(area, False, False, 0)
        tl = Gtk.Label(label=title)
        tl.get_style_context().add_class("big")
        f.card.pack_start(tl, False, False, 0)
        sl = Gtk.Label(label=sub)
        sl.get_style_context().add_class("sub")
        sl.set_no_show_all(not sub)
        f.card.pack_start(sl, False, False, 0)
        f.subtitle = sl
        action = (lambda: subprocess.Popen([str(SCRIPTS / "power-mode.sh"), "power-saver"])) if low else None
        f.show_for(5.0 if low else 2.8, clickable=action)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("test-charging", "test-low"):
        # Preview from Settings: ask the running copy to show it
        if not OSD_FIFO.is_fifo():
            sys.exit("desktop-extras isn't running")
        fd = os.open(OSD_FIFO, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, (sys.argv[1] + "\n").encode())
        os.close(fd)
        return
    if PID_FILE.exists():                       # one at a time: a new start replaces the old one
        try:
            os.kill(int(PID_FILE.read_text().strip()), 15)
            time.sleep(0.2)
        except (OSError, ValueError):
            pass
    PID_FILE.write_text(str(os.getpid()))
    import signal
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (Gtk.main_quit(), False)[1])
    try:
        Extras()
        Gtk.main()
    finally:
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
                OSD_FIFO.unlink()
                OSD_ON.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    main()
