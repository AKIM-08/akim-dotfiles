#!/usr/bin/env python3
"""quickpanel.py - Live quick panel (Super + N): media, toggles, sliders, notifications.

GTK3 on a layer-shell overlay. While open, a background thread reads the system state about
once a second (and immediately when PipeWire reports a volume change), so tiles and sliders
follow keyboard shortcuts and other apps without reopening the panel.

    Esc, Super + N again, or a click outside the panel closes it.
    Tiles: click toggles; right-click Wi-Fi / Bluetooth opens their menus.
    Notifications stay in SwayNC; the bottom row opens its list (Super + Shift + N).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

try:
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
except (ImportError, ValueError) as e:
    sys.stderr.write(f"quickpanel: GTK3 unavailable: {e}\n")
    sys.exit(1)

HAS_LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    HAS_LAYER_SHELL = True
except (ImportError, ValueError):
    pass

HOME = Path.home()
SCRIPTS = HOME / ".config" / "hypr" / "scripts"
ART_CACHE = HOME / ".cache" / "quickpanel"
PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "quickpanel.pid"
WIDTH = 380


# ------------------------------------------------------------------------------ helpers
def run(cmd, timeout=2.0) -> str:
    """Run a command (list or shell string), return stripped stdout ('' on any failure)."""
    try:
        out = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def spawn(cmd):
    try:
        subprocess.Popen(cmd, shell=isinstance(cmd, str), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        sys.stderr.write(f"quickpanel: {cmd}: {e}\n")


def have(cmd) -> bool:
    return shutil.which(cmd) is not None


def load_colors() -> dict:
    c = {"bg": "#1d2633", "fg": "#edf1f6", "accent": "#6f8fb8"}
    try:
        data = json.loads((HOME / ".cache" / "wal" / "colors.json").read_text())
        c["bg"] = data["special"]["background"]
        c["fg"] = data["special"]["foreground"]
        c["accent"] = data["colors"].get("color1") or c["accent"]
    except Exception:
        pass
    return c


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def fmt_time(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


# ------------------------------------------------------------------------------ state
def backlight_dir():
    """The backlight device brightnessctl uses (first one), read straight from sysfs."""
    devs = sorted(Path("/sys/class/backlight").glob("*"))
    return devs[0] if devs else None


BACKLIGHT = backlight_dir()


def read_brightness():
    if not BACKLIGHT:
        return None
    try:
        cur = int((BACKLIGHT / "brightness").read_text())
        top = int((BACKLIGHT / "max_brightness").read_text())
        return round(cur * 100 / top) if top else None
    except (OSError, ValueError):
        return None


def read_fast() -> dict:
    """What keys change: volume, mute, mic, brightness. Cheap; read ~4 times a second."""
    st = {}
    sink = run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])          # "Volume: 0.70 [MUTED]"
    try:
        st["volume"] = round(float(sink.split()[1]) * 100)
    except (IndexError, ValueError):
        st["volume"] = None
    st["mute"] = "MUTED" in sink
    st["mic_muted"] = "MUTED" in run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"])
    st["brightness"] = read_brightness()
    return st


def read_state() -> dict:
    """Everything else (network, Bluetooth, toggles, battery, media). Read about once a second."""
    st = {}

    # Wi-Fi
    st["wifi_on"] = run(["nmcli", "-t", "radio", "wifi"]) == "enabled"
    ssid = ""
    for line in run(["nmcli", "-t", "-e", "no", "-f", "ACTIVE,SSID", "dev", "wifi"]).splitlines():
        if line.startswith("yes:"):
            ssid = line[4:]
            break
    st["ssid"] = ssid

    # Bluetooth
    show = run(["bluetoothctl", "show"])
    st["bt_on"] = "Powered: yes" in show
    device = ""
    if st["bt_on"]:
        for line in run(["bluetoothctl", "devices", "Connected"]).splitlines():
            parts = line.split(" ", 2)
            if len(parts) == 3:
                device = parts[2]
                break
    st["bt_device"] = device

    # Toggles
    st["dnd"] = run(["swaync-client", "-D"]) == "true"
    night = run([str(SCRIPTS / "nightlight.sh"), "status"])
    st["night"] = night if night.isdigit() else ""
    st["caffeine"] = (HOME / ".cache" / "caffeine_active").exists()

    # Battery
    st["battery"] = None
    st["charging"] = False
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            st["battery"] = int((bat / "capacity").read_text().strip())
            st["charging"] = (bat / "status").read_text().strip() in ("Charging", "Full")
        except Exception:
            pass
        break

    # Notifications
    count = run(["swaync-client", "-c"])
    st["notifications"] = int(count) if count.isdigit() else 0

    # Media
    st["media"] = None
    if have("playerctl"):
        meta = run(["playerctl", "metadata", "--format",
                    "{{status}}\t{{title}}\t{{artist}}\t{{mpris:artUrl}}\t{{position}}\t{{mpris:length}}"])
        f = meta.split("\t")
        if len(f) == 6 and f[0] in ("Playing", "Paused") and f[1]:
            def num(v):
                try:
                    return int(v) / 1_000_000
                except ValueError:
                    return 0.0
            st["media"] = {"playing": f[0] == "Playing", "title": f[1], "artist": f[2], "art": f[3],
                           "position": num(f[4]), "length": num(f[5])}
    return st


def cover_path(url: str):
    """Local file for cover art (file:// directly, http(s) downloaded once into a cache)."""
    if not url:
        return None
    if url.startswith("file://"):
        p = urllib.request.url2pathname(url[7:])
        return p if os.path.isfile(p) else None
    if url.startswith(("http://", "https://")):
        ART_CACHE.mkdir(parents=True, exist_ok=True)
        dest = ART_CACHE / (hashlib.md5(url.encode()).hexdigest() + ".img")
        if not dest.exists():
            try:
                with urllib.request.urlopen(url, timeout=4) as r, open(dest, "wb") as out:
                    out.write(r.read(4_000_000))
            except Exception:
                return None
        return str(dest)
    return None


# ------------------------------------------------------------------------------ UI
class Tile(Gtk.Button):
    def __init__(self, icon, name, on_click, on_right=None):
        super().__init__()
        self.get_style_context().add_class("tile")
        self.set_focus_on_click(False)          # no dashed focus ring after a click
        self.set_can_focus(False)               # ...or when the panel opens
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.icon = Gtk.Label(label=icon)
        self.icon.get_style_context().add_class("tile-icon")
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.name = Gtk.Label(label=name, xalign=0)
        self.name.get_style_context().add_class("tile-name")
        self.sub = Gtk.Label(label="", xalign=0)
        self.sub.get_style_context().add_class("tile-sub")
        self.sub.set_ellipsize(3)                       # Pango.EllipsizeMode.END
        self.sub.set_max_width_chars(14)
        text.pack_start(self.name, False, False, 0)
        text.pack_start(self.sub, False, False, 0)
        box.pack_start(self.icon, False, False, 0)
        box.pack_start(text, True, True, 0)
        self.add(box)
        self.connect("clicked", lambda *_: on_click())
        if on_right:
            self.connect("button-press-event", lambda _w, e: (on_right(), True)[1] if e.button == 3 else False)

    def set_state(self, on: bool, sub: str):
        ctx = self.get_style_context()
        (ctx.add_class if on else ctx.remove_class)("on")
        if self.sub.get_text() != sub:
            self.sub.set_text(sub)


class QuickPanel(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("quickpanel")
        self.colors = load_colors()
        self.colors_mtime = None
        self.css_provider = None
        self.state = {}
        self.busy = False                 # a slow background read is running
        self.fast_busy = False            # a fast (volume/brightness) read is running
        self.fast_pending = False         # another fast read was requested meanwhile
        self.hold = {}                    # slider -> time until external updates are ignored
        self.last_art = None
        self.apply_css()

        self.set_app_paintable(True)
        screen = self.get_screen()
        if screen.get_rgba_visual() and screen.is_composited():
            self.set_visual(screen.get_rgba_visual())
        if HAS_LAYER_SHELL:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "quickpanel")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_exclusive_zone(self, -1)
            for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                         GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, edge, True)
        else:
            self.fullscreen()
            self.set_decorated(False)

        # Fullscreen transparent backdrop (click = close) holding the panel in the top-left
        backdrop = Gtk.EventBox()
        backdrop.connect("button-press-event", self.on_backdrop)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        panel.get_style_context().add_class("panel")
        panel.set_size_request(WIDTH, -1)
        panel.set_halign(Gtk.Align.START)
        panel.set_valign(Gtk.Align.START)
        panel.set_margin_top(12)
        panel.set_margin_start(12)
        self.panel_box = Gtk.EventBox()
        self.panel_box.add(panel)
        self.panel_box.set_halign(Gtk.Align.START)
        self.panel_box.set_valign(Gtk.Align.START)
        self.panel_box.connect("button-press-event", lambda *_: True)    # clicks inside stay inside
        backdrop.add(self.panel_box)
        self.add(backdrop)

        panel.pack_start(self.build_header(), False, False, 0)
        self.media = self.build_media()
        panel.pack_start(self.media, False, False, 0)
        panel.pack_start(self.build_tiles(), False, False, 0)
        panel.pack_start(self.build_sliders(), False, False, 0)
        panel.pack_start(self.build_notifications(), False, False, 0)

        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)
        self.refresh()
        GLib.timeout_add(1000, self.refresh)
        GLib.timeout_add(250, self.refresh_fast)
        GLib.timeout_add(1000, self.tick_media)
        threading.Thread(target=self.watch_audio, daemon=True).start()

    # -------------------------------------------------------------- styling
    def apply_css(self):
        bg, fg, acc = self.colors["bg"], self.colors["fg"], self.colors["accent"]
        css = f"""
        * {{ font-family: "JetBrainsMono Nerd Font", monospace; color: {fg}; }}
        window {{ background: transparent; }}
        .panel {{
            background: {rgba(bg, 0.80)}; border: 1px solid {rgba(fg, 0.14)};
            border-radius: 22px; padding: 18px;
        }}
        .time {{ font-size: 28px; font-weight: 800; }}
        .date, .battery, .dim {{ color: {rgba(fg, 0.62)}; font-size: 12px; }}
        button {{ background: none; border: none; box-shadow: none; padding: 0; }}
        * {{ outline-style: none; outline-width: 0; outline-offset: 0; }}
        .round {{
            background: {rgba(fg, 0.12)}; border-radius: 99px; min-width: 34px; min-height: 34px;
            font-size: 15px;
        }}
        .round:hover {{ background: {rgba(fg, 0.22)}; }}
        .media {{
            background: {rgba(acc, 0.28)}; border-radius: 18px; padding: 12px;
        }}
        .media-title {{ font-weight: 700; font-size: 13px; }}
        .media-artist {{ color: {rgba(fg, 0.7)}; font-size: 11px; }}
        .play {{ background: {fg}; color: {bg}; min-width: 40px; min-height: 40px; }}
        .play label {{ color: {bg}; }}
        .play:hover {{ background: {rgba(fg, 0.85)}; }}
        .tile {{
            background: {rgba(fg, 0.10)}; border-radius: 16px; padding: 9px 11px;
            min-height: 42px;
        }}
        .tile:hover {{ background: {rgba(fg, 0.16)}; }}
        .tile.on {{ background: {acc}; }}
        .tile.on:hover {{ background: {rgba(acc, 0.85)}; }}
        .tile-icon {{
            background: {rgba(fg, 0.14)}; border-radius: 99px; min-width: 32px; min-height: 32px;
            font-size: 15px;
        }}
        .tile.on .tile-icon {{ background: {rgba(fg, 0.25)}; }}
        .tile-name {{ font-weight: 700; font-size: 12px; }}
        .tile-sub {{ color: {rgba(fg, 0.62)}; font-size: 10.5px; }}
        .tile.on .tile-sub {{ color: {rgba(fg, 0.85)}; }}
        scale trough {{ background: {rgba(fg, 0.18)}; border-radius: 99px; min-height: 6px; border: none; }}
        scale highlight {{ background: {acc}; border-radius: 99px; border: none; }}
        scale slider {{ background: {fg}; border-radius: 99px; min-width: 14px; min-height: 14px; border: none; box-shadow: none; }}
        .media scale highlight {{ background: {fg}; }}
        .slider-icon {{ font-size: 15px; min-width: 22px; }}
        .notif {{ background: {rgba(fg, 0.10)}; border-radius: 16px; padding: 11px 14px; }}
        .notif:hover {{ background: {rgba(fg, 0.16)}; }}
        .count {{ background: {acc}; border-radius: 99px; padding: 1px 9px; font-weight: 700; }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        if self.css_provider:                       # re-theme: replace the previous colors
            Gtk.StyleContext.remove_provider_for_screen(screen, self.css_provider)
        Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.css_provider = provider

    @staticmethod
    def round_button(text, action, extra=None):
        b = Gtk.Button(label=text)
        b.set_focus_on_click(False)
        b.set_can_focus(False)
        b.get_style_context().add_class("round")
        if extra:
            b.get_style_context().add_class(extra)
        b.connect("clicked", lambda *_: action())
        return b

    # -------------------------------------------------------------- sections
    def build_header(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        times = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.time_label = Gtk.Label(xalign=0)
        self.time_label.get_style_context().add_class("time")
        self.date_label = Gtk.Label(xalign=0)
        self.date_label.get_style_context().add_class("date")
        times.pack_start(self.time_label, False, False, 0)
        times.pack_start(self.date_label, False, False, 0)
        box.pack_start(times, False, False, 0)
        self.battery_label = Gtk.Label()
        self.battery_label.get_style_context().add_class("battery")
        box.pack_end(self.round_button("\U000f0425", self.open_power), False, False, 0)
        box.pack_end(self.round_button("\U000f0493", self.open_settings), False, False, 0)
        box.pack_end(self.battery_label, False, False, 6)
        return box

    def build_media(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("media")
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.art = Gtk.Image()
        self.art.set_size_request(64, 64)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_valign(Gtk.Align.CENTER)
        self.m_title = Gtk.Label(xalign=0)
        self.m_title.get_style_context().add_class("media-title")
        self.m_title.set_ellipsize(3)
        self.m_title.set_max_width_chars(26)
        self.m_artist = Gtk.Label(xalign=0)
        self.m_artist.get_style_context().add_class("media-artist")
        self.m_artist.set_ellipsize(3)
        self.m_artist.set_max_width_chars(30)
        info.pack_start(self.m_title, False, False, 0)
        info.pack_start(self.m_artist, False, False, 0)
        top.pack_start(self.art, False, False, 0)
        top.pack_start(info, True, True, 0)

        prog = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.m_pos = Gtk.Label(label="0:00")
        self.m_pos.get_style_context().add_class("dim")
        self.m_len = Gtk.Label(label="0:00")
        self.m_len.get_style_context().add_class("dim")
        self.m_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.m_scale.set_draw_value(False)
        self.m_scale.set_can_focus(False)
        self.m_scale.connect("button-press-event", lambda *_: self.hold.__setitem__("seek", time.time() + 30) or False)
        self.m_scale.connect("button-release-event", self.on_seek)
        prog.pack_start(self.m_pos, False, False, 0)
        prog.pack_start(self.m_scale, True, True, 0)
        prog.pack_start(self.m_len, False, False, 0)

        ctl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        ctl.set_halign(Gtk.Align.CENTER)
        ctl.pack_start(self.round_button("\U000f04ae", lambda: self.media_cmd("previous")), False, False, 0)
        self.play_btn = self.round_button("\U000f03e4", lambda: self.media_cmd("play-pause"), "play")
        ctl.pack_start(self.play_btn, False, False, 0)
        ctl.pack_start(self.round_button("\U000f04ad", lambda: self.media_cmd("next")), False, False, 0)

        card.pack_start(top, False, False, 0)
        card.pack_start(prog, False, False, 0)
        card.pack_start(ctl, False, False, 0)
        return card

    def build_tiles(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        S = str(SCRIPTS)
        self.tiles = {
            "wifi": Tile("\U000f0928", "Wi-Fi", self.toggle_wifi, lambda: self.close_then(f"{S}/wifi-menu.sh")),
            "bt": Tile("\U000f00af", "Bluetooth", lambda: self.act(f"{S}/toggle-bluetooth.sh"),
                       lambda: self.close_then(f"{S}/bluetooth-menu.sh")),
            "mute": Tile("\U000f075f", "Mute", lambda: self.act(f"{S}/volume-mute.sh")),
            "mic": Tile("\U000f036d", "Mic off", lambda: self.act(f"{S}/mic-mute.sh")),
            "dnd": Tile("\U000f009b", "Do Not Disturb", lambda: self.act("swaync-client -d -sw")),
            "night": Tile("\U000f0594", "Night light", lambda: self.act(f"{S}/nightlight.sh toggle")),
            "caffeine": Tile("\U000f0176", "Caffeine", lambda: self.act(f"bash {S}/caffeine-toggle.sh")),
            "shot": Tile("\U000f0100", "Screenshot", lambda: self.close_then(f"sleep 0.35; {S}/screenshot.sh region")),
            "screens": Tile("\U000f0379", "Screens", lambda: self.close_then(f"python3 {S}/overlay_menu.py screens")),
        }
        for i, tile in enumerate(self.tiles.values()):
            grid.attach(tile, i % 2, i // 2, 1, 1)
        return grid

    def build_sliders(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        def row(icon, setter, key):
            r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            ic = Gtk.Label(label=icon)
            ic.get_style_context().add_class("slider-icon")
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            scale.set_draw_value(False)
            scale.set_can_focus(False)
            value = Gtk.Label(label="")
            value.get_style_context().add_class("dim")
            value.set_width_chars(4)

            def changed(s):
                v = int(s.get_value())
                value.set_text(f"{v}%")
                if getattr(s, "_programmatic", False):
                    return
                self.hold[key] = time.time() + 1.2                # ignore our own stale reads briefly
                setter(v)
            scale.connect("value-changed", changed)
            r.pack_start(ic, False, False, 0)
            r.pack_start(scale, True, True, 0)
            r.pack_start(value, False, False, 0)
            box.pack_start(r, False, False, 0)
            return scale, value

        self.vol_scale, _ = row("\U000f057e", lambda v: spawn(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{v}%"]), "volume")
        self.bri_scale, _ = row("\U000f00df", lambda v: spawn(["brightnessctl", "-q", "set", f"{max(v, 1)}%"]), "brightness")
        return box

    def build_notifications(self):
        b = Gtk.Button()
        b.set_focus_on_click(False)
        b.set_can_focus(False)
        b.get_style_context().add_class("notif")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.pack_start(Gtk.Label(label="\U000f009a"), False, False, 0)
        lab = Gtk.Label(label="Notifications", xalign=0)
        lab.get_style_context().add_class("tile-name")
        box.pack_start(lab, True, True, 0)
        self.count_label = Gtk.Label(label="0")
        self.count_label.get_style_context().add_class("count")
        box.pack_start(self.count_label, False, False, 0)
        box.pack_start(Gtk.Label(label="\U000f0142"), False, False, 0)
        b.add(box)
        b.connect("clicked", lambda *_: self.close_then("swaync-client -op -sw"))
        return b

    # -------------------------------------------------------------- actions
    def act(self, cmd):
        spawn(cmd)
        GLib.timeout_add(250, self.refresh_once)

    def close_then(self, cmd):
        spawn(f"sleep 0.15; {cmd}")
        Gtk.main_quit()

    def toggle_wifi(self):
        self.act(["nmcli", "radio", "wifi", "off" if self.state.get("wifi_on") else "on"])

    def media_cmd(self, what):
        spawn(["playerctl", what])
        GLib.timeout_add(200, self.refresh_once)

    def on_seek(self, scale, _event):
        spawn(["playerctl", "position", str(int(scale.get_value()))])
        self.hold["seek"] = time.time() + 1.5
        return False

    def open_settings(self):
        self.close_then(f"python3 {SCRIPTS / 'settings.py'}")

    def open_power(self):
        self.close_then(str(SCRIPTS / "snmenu-toggle.sh"))

    def on_backdrop(self, _w, event):
        Gtk.main_quit()
        return True

    def on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()
            return True
        return False

    # -------------------------------------------------------------- updates
    def refresh_once(self):
        self.refresh()
        self.refresh_fast()
        return False

    def refresh(self):
        """Slow cycle (~1 s): clock, colors, network, Bluetooth, toggles, battery, media."""
        self.time_label.set_text(time.strftime("%H:%M"))
        self.date_label.set_text(time.strftime("%a %d %b"))
        self.reload_colors_if_changed()
        if not self.busy:
            self.busy = True
            threading.Thread(target=self._read, daemon=True).start()
        return True

    def refresh_fast(self):
        """Fast cycle (~250 ms and on every PipeWire event): volume, mute, mic, brightness.
        A request that arrives during a read is remembered and run right after it."""
        if self.fast_busy:
            self.fast_pending = True
        else:
            self.fast_busy = True
            threading.Thread(target=self._read_fast, daemon=True).start()
        return True

    def refresh_fast_once(self):
        self.refresh_fast()
        return False

    def _read(self):
        try:
            st = read_state()
            art = cover_path(st["media"]["art"]) if st.get("media") else None
        except Exception as e:
            sys.stderr.write(f"quickpanel: {e}\n")
            st, art = None, None
        GLib.idle_add(self._apply, st, art)

    def _read_fast(self):
        try:
            st = read_fast()
        except Exception as e:
            sys.stderr.write(f"quickpanel: {e}\n")
            st = None
        GLib.idle_add(self._apply_fast, st)

    def _apply_fast(self, st):
        self.fast_busy = False
        if st:
            self.state.update(st)
            self.tiles["mute"].set_state(st["mute"], "Sound off" if st["mute"] else "Sound on")
            self.tiles["mic"].set_state(st["mic_muted"], "Muted" if st["mic_muted"] else "Listening")
            self.set_scale(self.vol_scale, st["volume"], "volume")
            self.set_scale(self.bri_scale, st["brightness"], "brightness")
            self.bri_scale.get_parent().set_visible(st["brightness"] is not None)
        if self.fast_pending:
            self.fast_pending = False
            self.refresh_fast()
        return False

    def reload_colors_if_changed(self):
        """Follow wallpaper changes while open: re-theme when the pywal palette changes."""
        try:
            mtime = (HOME / ".cache" / "wal" / "colors.json").stat().st_mtime
        except OSError:
            return
        if mtime != self.colors_mtime:
            self.colors_mtime = mtime
            self.colors = load_colors()
            self.apply_css()

    def set_scale(self, scale, value, key):
        if value is None or time.time() < self.hold.get(key, 0):
            return
        if int(scale.get_value()) != value:
            scale._programmatic = True
            scale.set_value(value)
            scale._programmatic = False

    def _apply(self, st, art):
        self.busy = False
        if not st:
            return False
        self.state.update(st)
        t = self.tiles
        t["wifi"].set_state(st["wifi_on"], st["ssid"] or ("Not connected" if st["wifi_on"] else "Off"))
        t["bt"].set_state(st["bt_on"], st["bt_device"] or ("No device" if st["bt_on"] else "Off"))
        t["dnd"].set_state(st["dnd"], "On" if st["dnd"] else "Off")
        t["night"].set_state(bool(st["night"]), f"{st['night']}K" if st["night"] else "Off")
        t["caffeine"].set_state(st["caffeine"], "Staying awake" if st["caffeine"] else "Off")
        t["shot"].set_state(False, "Region")

        bat = st["battery"]
        bat_icon = "\U000f0084" if st["charging"] else "\U000f0079"
        self.battery_label.set_text("" if bat is None else f"{bat_icon} {bat}%")
        self.count_label.set_text(str(st["notifications"]))

        m = st["media"]
        if m:
            self.media.set_visible(True)
            self.m_title.set_text(m["title"])
            self.m_artist.set_text(m["artist"])
            self.play_btn.set_label("\U000f03e4" if m["playing"] else "\U000f040a")
            self.media_info = dict(m, at=time.time())
            if m["length"] > 0:
                self.m_scale.set_range(0, m["length"])
                self.m_len.set_text(fmt_time(m["length"]))
            if time.time() >= self.hold.get("seek", 0):
                self.m_scale.set_value(m["position"])
                self.m_pos.set_text(fmt_time(m["position"]))
            if art != self.last_art:
                self.last_art = art
                try:
                    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(art, 64, 64, True) if art else None
                except Exception:
                    pix = None
                if pix:
                    self.art.set_from_pixbuf(pix)
                else:
                    self.art.clear()
        else:
            self.media.set_visible(False)
        return False

    def tick_media(self):
        """Advance the progress bar smoothly between reads."""
        info = getattr(self, "media_info", None)
        if info and info["playing"] and time.time() >= self.hold.get("seek", 0):
            pos = min(info["position"] + (time.time() - info["at"]), info["length"] or 1e9)
            self.m_scale.set_value(pos)
            self.m_pos.set_text(fmt_time(pos))
        return True

    def watch_audio(self):
        """Refresh right away when PipeWire/Pulse reports a sink or source change."""
        if not have("pactl"):
            return
        try:
            proc = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, text=True,
                                    stderr=subprocess.DEVNULL, preexec_fn=die_with_parent)
        except Exception:
            return
        self.audio_proc = proc                      # stopped in main() when the panel closes
        last = 0.0
        for line in proc.stdout:
            if "'change' on sink" in line or "'change' on source" in line:
                now = time.time()
                if now - last > 0.15:
                    last = now
                    GLib.idle_add(self.refresh_fast_once)


def die_with_parent():
    """For watcher subprocesses: the kernel stops them when this program ends, however it ends."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, 15)   # PR_SET_PDEATHSIG, SIGTERM
    except (OSError, AttributeError):
        pass


def main():
    # Toggle: a second launch closes the open panel
    if PID_FILE.exists():
        try:
            os.kill(int(PID_FILE.read_text().strip()), 15)
            PID_FILE.unlink(missing_ok=True)
            return
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    win = None
    try:
        # Closing with the shortcut sends SIGTERM: quit the main loop so `finally` runs
        import signal
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (Gtk.main_quit(), False)[1])
        win = QuickPanel()
        win.show_all()
        win.media.set_visible(False)
        win.refresh_once()
        Gtk.main()
    finally:
        proc = getattr(win, "audio_proc", None)
        if proc and proc.poll() is None:
            proc.terminate()
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
