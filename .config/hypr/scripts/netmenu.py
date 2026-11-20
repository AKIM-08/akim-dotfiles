#!/usr/bin/env python3
"""netmenu.py - Wi-Fi and Bluetooth menus, drawn as overlays (bar icons, quick panel, island).

    netmenu.py wifi        popover under the bar: switch, your network, the others; a locked one
                           asks for its password in its own row. "Radar" switches view.
    netmenu.py wifi-radar  networks as dots around you, nearer the middle when stronger
    netmenu.py bt          popover: switch, connected devices with battery, paired ones;
                           "All devices" and "Search" switch view
    netmenu.py bt-cards    a card per device with a battery ring; "Add a device" searches
    netmenu.py bt-radar    pairing: nearby devices appear around you while it scans; click to pair

Esc or a click outside closes; Backspace goes back to the popover; the same command again
closes it. Wi-Fi through NetworkManager (nmcli), Bluetooth through BlueZ (bluetoothctl).
"""

import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk   # noqa: E402
import cairo                                # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ImportError, ValueError):
    GtkLayerShell = None

HOME = Path.home()
SCRIPTS = Path(__file__).resolve().parent
PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "netmenu.pid"
NERD = '"JetBrainsMono Nerd Font"'
G = {"wifi": "\U000f05a9", "bt": "\U000f00af", "lock": "\U000f033e", "check": "\U000f012c", "radar": "\U000f0437",
     "search": "\U000f0349", "gear": "\U000f0493", "back": "\U000f004d", "plus": "\U000f0415", "off": "\U000f05aa",
     "headset": "\U000f02cb", "speaker": "\U000f04c3", "mouse": "\U000f037d", "keyboard": "\U000f030c",
     "phone": "\U000f03f2", "laptop": "\U000f0322", "gamepad": "\U000f02b4", "watch": "\U000f0589"}
SIGNAL = ["\U000f092f", "\U000f091f", "\U000f0922", "\U000f0925", "\U000f0928"]


# ------------------------------------------------------------------------------ helpers
def run(cmd, timeout=6):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def have(cmd):
    return shutil.which(cmd) is not None


def notify(title, body):
    subprocess.Popen(["notify-send", "-e", "-a", title, "-u", "low", "-h", f"string:x-canonical-private-synchronous:{title}",
                      title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def palette():
    c = {"bg": "#141824", "fg": "#eef1f7", "accent": "#7aa2f7"}
    try:
        d = json.loads((HOME / ".cache" / "wal" / "colors.json").read_text(encoding="utf-8"))
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


def lab(text="", *classes, xalign=0.0, ellipsize=False):
    w = Gtk.Label(label=text)
    w.set_xalign(xalign)
    if ellipsize:
        w.set_ellipsize(3)
        w.set_max_width_chars(28)
    for c in classes:
        w.get_style_context().add_class(c)
    return w


def pill(text, on_click, accent=False, glyph=None):
    b = Gtk.Button()
    b.set_can_focus(False)
    box = Gtk.Box(spacing=6)
    if glyph:
        box.pack_start(lab(glyph, "glyph"), False, False, 0)
    box.pack_start(lab(text), False, False, 0)
    b.add(box)
    b.get_style_context().add_class("pill")
    if accent:
        b.get_style_context().add_class("on")
    b.connect("clicked", lambda *_: on_click())
    return b


# ------------------------------------------------------------------------------ Wi-Fi (nmcli)
def nm_fields(line):
    """Split a terse nmcli line on unescaped colons."""
    out, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def wifi_state(rescan=False):
    st = {"on": run(["nmcli", "-t", "radio", "wifi"]).strip() == "enabled", "nets": [], "iface": "", "known": set()}
    for line in run(["nmcli", "-t", "-f", "DEVICE,TYPE", "dev"]).splitlines():
        f = nm_fields(line)
        if len(f) >= 2 and f[1] == "wifi":
            st["iface"] = f[0]
            break
    for line in run(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show"]).splitlines():
        f = nm_fields(line)
        if len(f) >= 2 and f[1].endswith("wireless"):
            st["known"].add(f[0])
    seen = {}
    out = run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ,RATE", "dev", "wifi", "list",
               "--rescan", "yes" if rescan else "no"], timeout=15)
    for line in out.splitlines():
        f = nm_fields(line)
        if len(f) < 6 or not f[1]:
            continue
        try:
            sig = int(f[2])
        except ValueError:
            sig = 0
        net = {"active": f[0].strip() == "*", "ssid": f[1], "signal": sig, "secure": f[3] not in ("", "--"),
               "band": "5 GHz" if f[4].startswith("5") else ("6 GHz" if f[4].startswith("6") else "2.4 GHz"), "rate": f[5]}
        old = seen.get(net["ssid"])
        if not old or net["active"] or (not old["active"] and net["signal"] > old["signal"]):
            seen[net["ssid"]] = net
    st["nets"] = sorted(seen.values(), key=lambda n: (not n["active"], -n["signal"]))
    return st


# ------------------------------------------------------------------------------ Bluetooth (bluetoothctl)
def bt_icon(icon):
    return {"audio-headset": "headset", "audio-headphones": "headset", "audio-card": "speaker", "input-mouse": "mouse",
            "input-keyboard": "keyboard", "input-gaming": "gamepad", "phone": "phone", "computer": "laptop"}.get(icon, "bt")


def bt_state():
    st = {"on": "Powered: yes" in run(["bluetoothctl", "show"]), "devices": []}
    for line in run(["bluetoothctl", "devices"]).splitlines():
        parts = line.split(" ", 2)
        if len(parts) < 3 or parts[0] != "Device":
            continue
        mac, name = parts[1], parts[2]
        info = run(["bluetoothctl", "info", mac], timeout=3)

        def field(key):
            m = re.search(rf"^\s*{key}:\s*(.+)$", info, re.M)
            return m.group(1).strip() if m else ""
        batt = re.search(r"Battery Percentage:.*\((\d+)\)", info)
        rssi_m = re.search(r"RSSI:.*?\((-?\d+)\)", info) or re.search(r"RSSI:\s*(-?\d+)", info)
        st["devices"].append({
            "mac": mac, "name": field("Alias") or name, "icon": bt_icon(field("Icon")),
            "paired": field("Paired") == "yes", "connected": field("Connected") == "yes",
            "battery": int(batt.group(1)) if batt else None,
            "rssi": int(rssi_m.group(1)) if rssi_m else None,
        })
    st["devices"].sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return st


def in_thread(work, then):
    def go():
        try:
            r = work()
        except Exception as e:
            sys.stderr.write(f"netmenu: {e!r}\n")
            r = None
        GLib.idle_add(lambda: (then(r), False)[1])
    threading.Thread(target=go, daemon=True).start()


# ------------------------------------------------------------------------------ the overlay
class NetMenu(Gtk.Window):
    def __init__(self, view):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("netmenu")
        self.set_app_paintable(True)
        if self.get_screen().get_rgba_visual():
            self.set_visual(self.get_screen().get_rgba_visual())
        if GtkLayerShell:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "overlay-menu")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_exclusive_zone(self, -1)
            for e in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, e, True)
        else:
            self.fullscreen()
        self.pal = palette()
        self.css()
        self.backdrop = Gtk.EventBox()
        self.backdrop.connect("button-press-event", lambda *_: (Gtk.main_quit(), True)[1])
        self.add(self.backdrop)
        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)
        self.view, self.child, self.timer, self.tick_id = None, None, None, None
        self.scan_proc = None
        self.wifi, self.bt = None, None
        self.busy = False
        self.switch(view)

    # -------------------------------------------------------------- style
    def css(self):
        a, b, f = self.pal["accent"], self.pal["bg"], self.pal["fg"]
        k = ink(a)
        css = f"""
        * {{ font-family: "Inter", {NERD}, sans-serif; color: {f}; outline-style: none; outline-width: 0; text-shadow: none; }}
        window {{ background: transparent; }}
        .dim {{ background: rgba(0,0,0,0.32); }}
        .clear {{ background: transparent; }}
        .glyph {{ font-family: {NERD}; }}
        .sub {{ color: {rgba(f, .55)}; font-size: 11px; }}
        .title {{ font-size: 16px; font-weight: 700; }}
        .big-title {{ font-size: 22px; font-weight: 700; }}
        .section {{ font-size: 10.5px; font-weight: 700; letter-spacing: 1px; color: {rgba(f, .5)}; margin: 8px 6px 2px; }}
        .popover {{ background: {rgba(b, .93)}; border: 1px solid {rgba(f, .14)}; border-radius: 20px; padding: 14px; }}
        list, viewport, scrolledwindow {{ background: transparent; border: none; }}
        row {{ background: transparent; border-radius: 12px; padding: 6px 8px; }}
        row:hover {{ background: {rgba(f, .07)}; }}
        row:selected {{ background: {rgba(a, .22)}; }}
        .current {{ background: {rgba(a, .16)}; border: 1px solid {rgba(a, .5)}; border-radius: 12px; padding: 8px 10px; }}
        .accent {{ color: {a}; }}
        button {{ background: none; background-image: none; border: none; box-shadow: none; text-shadow: none; padding: 0; min-height: 0; }}
        .pill {{ background: {rgba(f, .10)}; border-radius: 99px; padding: 5px 12px; }}
        .pill:hover {{ background: {rgba(f, .18)}; }}
        .pill.on {{ background: {a}; }}
        .pill.on label {{ color: {k}; }}
        entry {{ background: {rgba(f, .08)}; border: none; box-shadow: none; border-radius: 10px; padding: 6px 10px; caret-color: {a}; }}
        switch {{ background: {rgba(f, .22)}; border: none; border-radius: 99px; min-width: 44px; min-height: 24px; }}
        switch:checked {{ background: {a}; }}
        switch slider {{ background: #ffffff; border: none; border-radius: 99px; min-width: 20px; min-height: 20px; box-shadow: none; margin: 2px; }}
        .battery trough, levelbar trough {{ background: {rgba(f, .18)}; border: none; border-radius: 4px; min-height: 7px; min-width: 34px; padding: 0; }}
        levelbar block.filled {{ background: {a}; border-radius: 4px; border: none; }}
        levelbar block.empty {{ background: transparent; border: none; }}
        flowbox, flowboxchild {{ background: transparent; padding: 0; }}
        .devcard {{ background: {rgba(b, .84)}; border: 1px solid {rgba(f, .12)}; border-radius: 22px; padding: 16px 12px; min-width: 150px; }}
        .devcard.off {{ opacity: 0.72; }}
        flowboxchild:selected .devcard {{ border: 2px solid {a}; }}
        .addcard {{ border-style: dashed; background: {rgba(b, .5)}; }}
        .hint {{ color: {rgba(f, .7)}; font-size: 12px; }}
        .card {{ background: {rgba(b, .93)}; border: 1px solid {rgba(f, .14)}; border-radius: 16px; padding: 12px; }}
        """
        prov = Gtk.CssProvider()
        prov.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # -------------------------------------------------------------- views
    def switch(self, view):
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        if view != "bt-radar":
            self.stop_scan()
        if self.child:
            self.backdrop.remove(self.child)
        self.view = view
        ctx = self.backdrop.get_style_context()
        popover = view in ("wifi", "bt")
        ctx.remove_class("dim" if popover else "clear")
        ctx.add_class("clear" if popover else "dim")
        holder = Gtk.EventBox()
        holder.connect("button-press-event", lambda *_: True)
        content = {"wifi": self.wifi_popover, "wifi-radar": self.wifi_radar, "bt": self.bt_popover,
                   "bt-cards": self.bt_cards, "bt-radar": self.bt_radar}[view]()
        if popover:
            self.place_popover(holder)
        else:
            holder.set_halign(Gtk.Align.FILL)
            holder.set_valign(Gtk.Align.FILL)
            holder.set_visible_window(False)
        holder.add(content)
        self.child = holder
        self.backdrop.add(holder)
        self.show_all()

    def place_popover(self, holder):
        """Hang the popover under (or next to) the bar, at the side where the status icons are."""
        try:
            st = json.loads((HOME / ".config" / "waybar" / "layout.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            st = {}
        pos, theme = st.get("position", "top"), st.get("theme", "capsule")
        if theme == "island":
            pos = "top"
        bar = 46 if theme != "island" else 40
        holder.set_halign(Gtk.Align.START if pos == "left" else Gtk.Align.END)
        holder.set_valign(Gtk.Align.END if pos == "bottom" else Gtk.Align.START)
        holder.set_margin_top(bar + 6 if pos == "top" else 12)
        holder.set_margin_bottom(bar + 6 if pos == "bottom" else 12)
        holder.set_margin_end(bar + 6 if pos == "right" else 14)
        holder.set_margin_start(bar + 6 if pos == "left" else 14)

    def refresh_every(self, ms, fn):
        self.timer = GLib.timeout_add(ms, lambda: (fn(), True)[1])

    # -------------------------------------------------------------- keys
    def on_key(self, _w, e):
        k = e.keyval
        if k == Gdk.KEY_Escape:
            Gtk.main_quit()
            return True
        if k == Gdk.KEY_BackSpace and self.view in ("wifi-radar", "bt-cards", "bt-radar"):
            if not isinstance(self.get_focus(), Gtk.Entry):
                self.switch("wifi" if self.view == "wifi-radar" else "bt")
                return True
        if self.view == "bt-cards" and hasattr(self, "cards"):
            kids = self.cards.get_children()
            if not kids:
                return False
            sel = self.cards.get_selected_children()
            i = sel[0].get_index() if sel else 0
            per_row = max(1, min(len(kids), 5))
            moves = {Gdk.KEY_Left: -1, Gdk.KEY_Right: 1, Gdk.KEY_Up: -per_row, Gdk.KEY_Down: per_row}
            if k in moves:
                j = i + moves[k]
                if 0 <= j < len(kids):
                    self.cards.select_child(kids[j])
                    kids[j].grab_focus()
                return True
            if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
                kids[i].action()
                return True
        if self.view in ("wifi-radar", "bt-radar") and k in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if isinstance(self.get_focus(), Gtk.Entry):
                return False
            items = self.radar_items()
            if items:
                if k in (Gdk.KEY_Left, Gdk.KEY_Right):
                    self.radar_sel = (self.radar_sel + (1 if k == Gdk.KEY_Right else -1)) % len(items)
                    self.radar.queue_draw()
                else:
                    self.radar_pick(items[self.radar_sel % len(items)])
            return True
        return False

    # ============================================================== Wi-Fi popover
    def wifi_popover(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("popover")
        box.set_size_request(360, -1)
        head = Gtk.Box(spacing=8)
        head.pack_start(lab(G["wifi"], "glyph", "accent"), False, False, 0)
        head.pack_start(lab("Wi-Fi", "title"), True, True, 0)
        self.wifi_switch = Gtk.Switch()
        self.wifi_switch.set_can_focus(False)
        self.wifi_switch.connect("notify::active", self.on_wifi_switch)
        head.pack_end(self.wifi_switch, False, False, 0)
        box.pack_start(head, False, False, 0)
        self.wifi_current = Gtk.Box()
        box.pack_start(self.wifi_current, False, False, 0)
        box.pack_start(lab("OTHER NETWORKS", "section"), False, False, 0)
        self.wifi_list = Gtk.ListBox()
        self.wifi_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.wifi_list.connect("row-activated", lambda _l, r: self.wifi_row_clicked(r))
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(330)
        scroll.set_propagate_natural_height(True)
        scroll.add(self.wifi_list)
        box.pack_start(scroll, False, False, 0)
        self.wifi_status = lab("", "sub", xalign=0.5)
        box.pack_start(self.wifi_status, False, False, 0)
        foot = Gtk.Box(spacing=8)
        foot.pack_start(pill("Radar", lambda: self.switch("wifi-radar"), glyph=G["radar"]), False, False, 0)
        foot.pack_end(pill("Settings…", self.wifi_settings, glyph=G["gear"]), False, False, 0)
        box.pack_start(foot, False, False, 4)
        self.load_wifi(rescan=False, then_rescan=True)
        self.refresh_every(6000, lambda: self.load_wifi(rescan=False))
        return box

    def load_wifi(self, rescan=False, then_rescan=False):
        if not have("nmcli"):
            self.wifi = {"on": False, "nets": [], "iface": "", "known": set()}
            self.show_wifi(self.wifi, "NetworkManager (nmcli) is not installed")
            return
        if then_rescan:                                      # opening: fill at once, then scan
            if self.wifi is None:
                self.wifi = wifi_state(False)
            self.show_wifi(self.wifi)
            self.wifi_status.set_text("Looking for networks…")
            in_thread(lambda: wifi_state(True), lambda st: self.show_wifi(st))
            return
        in_thread(lambda: wifi_state(rescan), lambda st: self.show_wifi(st))

    def show_wifi(self, st, message=""):
        if st is None or self.busy:
            return
        self.wifi = st
        if self.view == "wifi-radar":
            self.radar.queue_draw()
            return
        if self.view != "wifi":
            return
        self.wifi_switch._programmatic = True
        self.wifi_switch.set_active(st["on"])
        self.wifi_switch._programmatic = False
        for c in self.wifi_current.get_children():
            self.wifi_current.remove(c)
        cur = next((n for n in st["nets"] if n["active"]), None)
        if cur:
            row = Gtk.Box(spacing=10)
            row.get_style_context().add_class("current")
            row.pack_start(lab(SIGNAL[min(4, cur["signal"] // 20)], "glyph", "accent"), False, False, 0)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            texts.pack_start(lab(cur["ssid"], "title", ellipsize=True), False, False, 0)
            texts.pack_start(lab(f"Connected · {cur['band']} · {cur['rate']}", "sub"), False, False, 0)
            row.pack_start(texts, True, True, 0)
            row.pack_end(pill("Disconnect", self.wifi_disconnect), False, False, 0)
            self.wifi_current.pack_start(row, True, True, 0)
        for r in self.wifi_list.get_children():
            self.wifi_list.remove(r)
        for n in [n for n in st["nets"] if not n["active"]][:14]:
            row = Gtk.ListBoxRow()
            row.net = n
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            h = Gtk.Box(spacing=10)
            h.pack_start(lab(SIGNAL[min(4, n["signal"] // 20)], "glyph", "accent"), False, False, 0)
            h.pack_start(lab(n["ssid"], ellipsize=True), True, True, 0)
            if n["ssid"] in st["known"]:
                h.pack_end(lab("saved", "sub"), False, False, 0)
            if n["secure"]:
                h.pack_end(lab(G["lock"], "glyph", "sub"), False, False, 0)
            v.pack_start(h, False, False, 0)
            row.add(v)
            row.vbox = v
            self.wifi_list.add(row)
        self.wifi_list.show_all()
        self.wifi_current.show_all()
        if message:
            self.wifi_status.set_text(message)
        elif not st["on"]:
            self.wifi_status.set_text("Wi-Fi is off")
        elif not st["nets"]:
            self.wifi_status.set_text("No networks found")
        else:
            self.wifi_status.set_text("")

    def on_wifi_switch(self, sw, _p):
        if getattr(sw, "_programmatic", False):
            return
        on = sw.get_active()
        self.wifi_status.set_text("Turning Wi-Fi on…" if on else "Turning Wi-Fi off…")
        in_thread(lambda: run(["nmcli", "radio", "wifi", "on" if on else "off"]),
                  lambda _r: GLib.timeout_add(1500, lambda: (self.load_wifi(rescan=on), False)[1]))

    def wifi_row_clicked(self, row):
        n = row.net
        if n["secure"] and n["ssid"] not in self.wifi["known"]:
            if getattr(row, "pw_box", None):
                return
            pw = Gtk.Box(spacing=8)
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_placeholder_text("Password")
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
            entry.connect("icon-press", lambda e, *_: e.set_visibility(not e.get_visibility()))
            entry.connect("activate", lambda e: self.wifi_connect(n["ssid"], e.get_text()))
            pw.pack_start(entry, True, True, 0)
            pw.pack_start(pill("Join", lambda: self.wifi_connect(n["ssid"], entry.get_text()), accent=True), False, False, 0)
            row.vbox.pack_start(pw, False, False, 0)
            row.pw_box = pw
            pw.show_all()
            entry.grab_focus()
        else:
            self.wifi_connect(n["ssid"], None)

    def wifi_connect(self, ssid, password):
        self.busy = True
        status = getattr(self, "wifi_status", None)
        if status and self.view == "wifi":
            status.set_text(f"Connecting to {ssid}…")
        notify("Wi-Fi", f"Connecting to {ssid}…")

        def work():
            if password is None and ssid in (self.wifi or {}).get("known", set()):
                r = subprocess.run(["nmcli", "con", "up", "id", ssid], capture_output=True, text=True, timeout=40)
            elif password:
                r = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                                   capture_output=True, text=True, timeout=40)
                if r.returncode != 0:                        # don't keep a profile with a wrong password
                    subprocess.run(["nmcli", "con", "delete", "id", ssid], capture_output=True, timeout=10)
            else:
                r = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid], capture_output=True, text=True, timeout=40)
            return r

        def done(r):
            self.busy = False
            ok = r is not None and r.returncode == 0
            notify("Wi-Fi", f"Connected to {ssid}" if ok else f"Could not connect to {ssid}" +
                   (" (wrong password?)" if password else ""))
            if ok:
                Gtk.main_quit()
            else:
                self.load_wifi()
        in_thread(work, done)

    def wifi_disconnect(self):
        iface = (self.wifi or {}).get("iface")
        if iface:
            in_thread(lambda: run(["nmcli", "dev", "disconnect", iface]), lambda _r: self.load_wifi())

    def wifi_settings(self):
        Gtk.main_quit()
        cmd = "nm-connection-editor" if have("nm-connection-editor") else "kitty --class nmtui -e nmtui"
        subprocess.Popen(["sh", "-c", f"sleep 0.15; {cmd}"], start_new_session=True)

    # ============================================================== radar (Wi-Fi and pairing)
    def radar_view(self, title, hint, draw_items):
        overlay = Gtk.Overlay()
        self.radar = Gtk.DrawingArea()
        self.radar.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.radar.connect("draw", self.draw_radar)
        self.radar.connect("button-press-event", self.radar_click)
        overlay.add(self.radar)
        self.radar_items_fn = draw_items
        self.radar_sel, self.radar_hits, self.radar_t0 = 0, [], time.monotonic()
        top = Gtk.Box(spacing=10)
        top.set_halign(Gtk.Align.CENTER)
        top.set_valign(Gtk.Align.START)
        top.set_margin_top(70)
        top.pack_start(pill("Back", lambda: self.switch("wifi" if self.view == "wifi-radar" else "bt"), glyph=G["back"]), False, False, 0)
        top.pack_start(lab(title, "big-title"), False, False, 0)
        overlay.add_overlay(top)
        self.radar_hint = lab(hint, "hint", xalign=0.5)
        self.radar_hint.set_valign(Gtk.Align.END)
        self.radar_hint.set_margin_bottom(46)
        overlay.add_overlay(self.radar_hint)
        self.radar_card = Gtk.Box(spacing=8)                 # password, when a locked network is chosen
        self.radar_card.get_style_context().add_class("card")
        self.radar_card.set_halign(Gtk.Align.CENTER)
        self.radar_card.set_valign(Gtk.Align.END)
        self.radar_card.set_margin_bottom(90)
        self.radar_card.set_no_show_all(True)
        overlay.add_overlay(self.radar_card)
        self.tick_id = self.radar.add_tick_callback(lambda *_: (self.radar.queue_draw(), True)[1])
        return overlay

    def radar_items(self):
        return self.radar_items_fn() if hasattr(self, "radar_items_fn") else []

    def draw_radar(self, w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()
        a = rgb(self.pal["accent"])
        cx, cy = W / 2, H * 0.5
        R = min(W, H) * 0.34
        t = time.monotonic() - self.radar_t0
        pulse = self.view == "bt-radar"
        for i, s in enumerate((1.0, 0.68, 0.36)):
            k = 1 + (0.04 * math.sin(t * 2.4 - i * 0.8) if pulse else 0)
            cr.set_source_rgba(*a, 0.32)
            cr.set_line_width(1.2)
            cr.arc(cx, cy, R * s * k, 0, 2 * math.pi)
            cr.stroke()
        if not pulse:                                        # sweeping beam
            ang = (t * 1.8) % (2 * math.pi)
            for j in range(26):
                cr.move_to(cx, cy)
                cr.arc(cx, cy, R, ang - (j + 1) * 0.025, ang - j * 0.025)
                cr.close_path()
                cr.set_source_rgba(*a, 0.30 * (1 - j / 26))
                cr.fill()
        cr.set_source_rgba(*a, 1)
        cr.arc(cx, cy, 30, 0, 2 * math.pi)
        cr.fill()
        self.text(cr, G["wifi"] if self.view == "wifi-radar" else G["bt"], cx, cy + 9, 26, ink_rgb=True)
        self.radar_hits = []
        items = self.radar_items()
        for idx, it in enumerate(items):
            r = R * (0.16 + 0.84 * (1 - it["strength"]))
            ang = (sum(map(ord, it["key"])) * 2.399) % (2 * math.pi)
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            sel = idx == self.radar_sel % max(1, len(items))
            glow = 0.55 + 0.45 * abs(math.sin(t * 2 + idx))
            size = 9 if it.get("strong") else 7
            if sel:
                cr.set_source_rgba(*a, 0.35)
                cr.arc(x, y, size + 8, 0, 2 * math.pi)
                cr.fill()
            if it.get("glyph"):
                cr.set_source_rgba(0.06, 0.07, 0.1, 0.9)
                cr.arc(x, y, 18, 0, 2 * math.pi)
                cr.fill()
                cr.set_source_rgba(*a, 1)
                cr.set_line_width(1.5)
                cr.arc(x, y, 18, 0, 2 * math.pi)
                cr.stroke()
                self.text(cr, it["glyph"], x, y + 7, 18, color=a)
            else:
                cr.set_source_rgba(*(a if it.get("active") else (1, 1, 1)), glow)
                cr.arc(x, y, size, 0, 2 * math.pi)
                cr.fill()
            lw = self.text(cr, it["label"], x, y + 36, 13, pill=True)
            self.radar_hits.append((x, y, lw, it))

    def text(self, cr, s, x, y, size, pill=False, color=None, ink_rgb=False):
        cr.select_font_face("JetBrainsMono Nerd Font", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(size)
        e = cr.text_extents(s)
        tx = x - e.width / 2 - e.x_bearing
        if pill:
            cr.set_source_rgba(0.05, 0.06, 0.09, 0.78)
            h = size + 10
            cr.new_sub_path()
            cr.arc(tx - 8 + h / 2, y - size + h / 2 - 5, h / 2, math.pi / 2, 3 * math.pi / 2)
            cr.arc(tx + e.width + 8 - h / 2, y - size + h / 2 - 5, h / 2, -math.pi / 2, math.pi / 2)
            cr.close_path()
            cr.fill()
        if ink_rgb:
            cr.set_source_rgba(*rgb(ink(self.pal["accent"])), 1)
        elif color:
            cr.set_source_rgba(*color, 1)
        else:
            cr.set_source_rgba(1, 1, 1, 0.95)
        cr.move_to(tx, y)
        cr.show_text(s)
        return e.width

    def radar_click(self, _w, e):
        for x, y, lw, it in self.radar_hits:
            on_dot = (e.x - x) ** 2 + (e.y - y) ** 2 < 26 ** 2
            on_label = abs(e.x - x) < lw / 2 + 12 and y + 18 <= e.y <= y + 46
            if on_dot or on_label:
                self.radar_sel = self.radar_hits.index((x, y, lw, it))
                self.radar_pick(it)
                return True
        if self.radar_card.get_visible():
            self.radar_card.hide()
        return True

    def radar_pick(self, it):
        it["action"]()

    # ============================================================== Wi-Fi radar
    def wifi_radar(self):
        if self.wifi is None and have("nmcli"):
            self.wifi = wifi_state(False)
        cur = next((n["ssid"] for n in (self.wifi or {}).get("nets", []) if n["active"]), None)
        hint = (f"Connected to {cur} · " if cur else "") + "click a network or ← → and Enter · Backspace: list · Esc closes"
        view = self.radar_view("Wi-Fi around you", hint, self.wifi_radar_items)
        in_thread(lambda: wifi_state(True), lambda st: self.show_wifi(st))
        self.refresh_every(8000, lambda: in_thread(lambda: wifi_state(True), lambda st: self.show_wifi(st)))
        return view

    def wifi_radar_items(self):
        out = []
        for n in (self.wifi or {}).get("nets", [])[:14]:
            out.append({"key": n["ssid"], "strength": n["signal"] / 100, "strong": n["signal"] >= 60, "active": n["active"],
                        "label": (G["lock"] + " " if n["secure"] else "") + n["ssid"],
                        "action": lambda n=n: self.radar_wifi_pick(n)})
        return out

    def radar_wifi_pick(self, n):
        if n["active"]:
            return
        if n["secure"] and n["ssid"] not in self.wifi["known"]:
            for c in self.radar_card.get_children():
                self.radar_card.remove(c)
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_placeholder_text(f"Password for {n['ssid']}")
            entry.set_width_chars(26)
            entry.connect("activate", lambda e: self.wifi_connect(n["ssid"], e.get_text()))
            self.radar_card.pack_start(lab(G["lock"], "glyph", "accent"), False, False, 0)
            self.radar_card.pack_start(entry, True, True, 0)
            self.radar_card.pack_start(pill("Join", lambda: self.wifi_connect(n["ssid"], entry.get_text()), accent=True), False, False, 0)
            # The card is "no show all" (hidden until needed), so show_all() would skip it: show
            # its children, then the card
            for c in self.radar_card.get_children():
                c.show_all()
            self.radar_card.show()
            entry.grab_focus()
        else:
            self.wifi_connect(n["ssid"], None)

    # ============================================================== Bluetooth popover
    def bt_popover(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("popover")
        box.set_size_request(350, -1)
        head = Gtk.Box(spacing=8)
        head.pack_start(lab(G["bt"], "glyph", "accent"), False, False, 0)
        head.pack_start(lab("Bluetooth", "title"), True, True, 0)
        self.bt_switch = Gtk.Switch()
        self.bt_switch.set_can_focus(False)
        self.bt_switch.connect("notify::active", self.on_bt_switch)
        head.pack_end(self.bt_switch, False, False, 0)
        box.pack_start(head, False, False, 0)
        self.bt_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self.bt_body, False, False, 0)
        self.bt_status = lab("", "sub", xalign=0.5)
        box.pack_start(self.bt_status, False, False, 0)
        foot = Gtk.Box(spacing=8)
        foot.pack_start(pill("Search", lambda: self.switch("bt-radar"), accent=True, glyph=G["search"]), False, False, 0)
        foot.pack_start(pill("All devices", lambda: self.switch("bt-cards")), False, False, 0)
        foot.pack_end(pill("Settings…", self.bt_settings, glyph=G["gear"]), False, False, 0)
        box.pack_start(foot, False, False, 6)
        self.load_bt(first=True)
        self.refresh_every(4000, self.load_bt)
        return box

    def load_bt(self, first=False):
        if not have("bluetoothctl"):
            self.bt = {"on": False, "devices": []}
            self.show_bt(self.bt, "BlueZ (bluetoothctl) is not installed")
            return
        if first:
            if self.bt is None:
                self.bt = bt_state()
            self.show_bt(self.bt)
            return
        if getattr(self, "bt_loading", False):              # one refresh at a time
            return
        self.bt_loading = True

        def done(st):
            self.bt_loading = False
            self.show_bt(st)
        in_thread(bt_state, done)

    def battery_widget(self, pct):
        bar = Gtk.LevelBar()
        bar.set_min_value(0)
        bar.set_max_value(100)
        bar.set_value(pct)
        bar.set_size_request(34, 7)
        bar.set_valign(Gtk.Align.CENTER)
        box = Gtk.Box(spacing=5)
        box.pack_start(bar, False, False, 0)
        box.pack_start(lab(f"{pct}%", "sub"), False, False, 0)
        return box

    def show_bt(self, st, message=""):
        if st is None or self.busy:
            return
        self.bt = st
        if self.view == "bt-cards":
            self.fill_bt_cards()
            return
        if self.view == "bt-radar":
            return
        if self.view != "bt":
            return
        self.bt_switch._programmatic = True
        self.bt_switch.set_active(st["on"])
        self.bt_switch._programmatic = False
        for c in self.bt_body.get_children():
            self.bt_body.remove(c)
        connected = [d for d in st["devices"] if d["connected"]]
        paired = [d for d in st["devices"] if d["paired"] and not d["connected"]]
        if connected:
            self.bt_body.pack_start(lab("CONNECTED", "section"), False, False, 0)
            for d in connected:
                row = Gtk.Box(spacing=10)
                row.get_style_context().add_class("current")
                row.pack_start(lab(G[d["icon"]], "glyph", "accent"), False, False, 0)
                row.pack_start(lab(d["name"], ellipsize=True), True, True, 0)
                if d["battery"] is not None:
                    row.pack_start(self.battery_widget(d["battery"]), False, False, 0)
                row.pack_end(pill("Disconnect", lambda d=d: self.bt_do("disconnect", d)), False, False, 0)
                self.bt_body.pack_start(row, False, False, 0)
        if paired:
            self.bt_body.pack_start(lab("PAIRED", "section"), False, False, 0)
            for d in paired[:8]:
                row = Gtk.Box(spacing=10)
                row.set_margin_start(10)
                row.set_margin_end(4)
                row.pack_start(lab(G[d["icon"]], "glyph"), False, False, 0)
                row.pack_start(lab(d["name"], ellipsize=True), True, True, 0)
                row.pack_end(pill("Connect", lambda d=d: self.bt_do("connect", d)), False, False, 0)
                self.bt_body.pack_start(row, False, False, 2)
        self.bt_body.show_all()
        if message:
            self.bt_status.set_text(message)
        elif not st["on"]:
            self.bt_status.set_text("Bluetooth is off")
        elif not connected and not paired:
            self.bt_status.set_text("No devices yet: Search to add one")
        else:
            self.bt_status.set_text("")

    def on_bt_switch(self, sw, _p):
        if getattr(sw, "_programmatic", False):
            return
        on = sw.get_active()
        self.bt_status.set_text("Turning Bluetooth on…" if on else "Turning Bluetooth off…")

        def work():
            if on:
                run(["rfkill", "unblock", "bluetooth"])
            return run(["bluetoothctl", "power", "on" if on else "off"])
        in_thread(work, lambda _r: GLib.timeout_add(800, lambda: (self.load_bt(), False)[1]))

    def bt_do(self, action, d):
        """connect / disconnect / pair (pair = pair + trust + connect), then refresh."""
        self.busy = True
        verb = {"connect": "Connecting to", "disconnect": "Disconnecting", "pair": "Pairing with"}[action]
        notify("Bluetooth", f"{verb} {d['name']}…")

        def work():
            if action == "pair":
                ok = subprocess.run(["bluetoothctl", "--timeout", "25", "pair", d["mac"]], capture_output=True, text=True, timeout=40)
                if "Failed" in ok.stdout and "AlreadyExists" not in ok.stdout:
                    return False
                run(["bluetoothctl", "trust", d["mac"]])
                action2 = "connect"
            else:
                action2 = action
            r = subprocess.run(["bluetoothctl", "--timeout", "20", action2, d["mac"]], capture_output=True, text=True, timeout=30)
            return "successful" in r.stdout.lower() or r.returncode == 0

        def done(ok):
            self.busy = False
            notify("Bluetooth", f"{d['name']}: " + ({"connect": "connected", "disconnect": "disconnected",
                                                     "pair": "paired and connected"}[action] if ok else "did not work"))
            if self.view == "bt-radar" and ok:
                self.switch("bt-cards")
            else:
                self.load_bt()
        in_thread(work, done)

    def bt_settings(self):
        Gtk.main_quit()
        subprocess.Popen(["sh", "-c", "sleep 0.15; blueman-manager"], start_new_session=True)

    # ============================================================== Bluetooth cards
    def bt_cards(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        head = Gtk.Box(spacing=10)
        head.set_halign(Gtk.Align.CENTER)
        head.pack_start(pill("Back", lambda: self.switch("bt"), glyph=G["back"]), False, False, 0)
        head.pack_start(lab(G["bt"], "glyph", "accent"), False, False, 0)
        head.pack_start(lab("Bluetooth", "big-title"), False, False, 0)
        box.pack_start(head, False, False, 0)
        self.cards = Gtk.FlowBox()
        self.cards.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.cards.set_max_children_per_line(5)
        self.cards.set_min_children_per_line(2)
        self.cards.set_homogeneous(True)
        self.cards.set_row_spacing(12)
        self.cards.set_column_spacing(12)
        self.cards.set_activate_on_single_click(False)
        self.cards.connect("child-activated", lambda _f, c: c.action())
        box.pack_start(self.cards, False, False, 0)
        box.pack_start(lab("Enter connects or disconnects · Backspace: back · Esc closes", "hint", xalign=0.5), False, False, 0)
        if self.bt is None:
            self.bt = bt_state() if have("bluetoothctl") else {"on": False, "devices": []}
        GLib.idle_add(lambda: (self.fill_bt_cards(), False)[1])
        self.refresh_every(4000, self.load_bt)
        return box

    def ring(self, pct, glyph, size=74):
        area = Gtk.DrawingArea()
        area.set_size_request(size, size)
        a = rgb(self.pal["accent"])

        def draw(w, cr):
            W, H = w.get_allocated_width(), w.get_allocated_height()
            cx, cy, r = W / 2, H / 2, min(W, H) / 2 - 4
            cr.set_line_width(5)
            cr.set_source_rgba(1, 1, 1, 0.12)
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.stroke()
            if pct is not None:
                cr.set_source_rgba(*a, 1)
                cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * pct / 100)
                cr.stroke()
            self.text(cr, glyph, cx, cy + 10, 26, color=a)
        area.connect("draw", draw)
        return area

    def fill_bt_cards(self):
        if not hasattr(self, "cards") or self.view != "bt-cards":
            return
        sel = self.cards.get_selected_children()
        sel_i = sel[0].get_index() if sel else 0
        for c in self.cards.get_children():
            self.cards.remove(c)
        for d in [d for d in self.bt["devices"] if d["paired"] or d["connected"]]:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("devcard")
            if not d["connected"]:
                card.get_style_context().add_class("off")
            card.pack_start(self.ring(d["battery"], G[d["icon"]]), False, False, 0)
            card.pack_start(lab(d["name"], "title", xalign=0.5, ellipsize=True), False, False, 0)
            sub = ((f"{d['battery']}% · " if d["battery"] is not None else "") + "Connected") if d["connected"] else "Paired"
            card.pack_start(lab(sub, "sub", xalign=0.5), False, False, 0)
            act = "disconnect" if d["connected"] else "connect"
            b = pill(act.capitalize(), lambda d=d, act=act: self.bt_do(act, d), accent=not d["connected"])
            b.set_halign(Gtk.Align.CENTER)
            card.pack_start(b, False, False, 0)
            child = Gtk.FlowBoxChild()
            child.add(card)
            child.action = lambda d=d, act=act: self.bt_do(act, d)
            self.cards.add(child)
        add = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add.get_style_context().add_class("devcard")
        add.get_style_context().add_class("addcard")
        add.set_valign(Gtk.Align.FILL)
        add.pack_start(lab(G["plus"], "glyph", "accent", xalign=0.5), True, False, 0)
        add.pack_start(lab("Add a device", xalign=0.5), False, False, 0)
        ev = Gtk.EventBox()
        ev.add(add)
        ev.connect("button-press-event", lambda *_: (self.switch("bt-radar"), True)[1])
        child = Gtk.FlowBoxChild()
        child.add(ev)
        child.action = lambda: self.switch("bt-radar")
        self.cards.add(child)
        self.cards.show_all()
        c = self.cards.get_child_at_index(min(sel_i, len(self.cards.get_children()) - 1))
        if c:
            self.cards.select_child(c)
            c.grab_focus()

    # ============================================================== Bluetooth pairing radar
    def bt_radar(self):
        if self.bt is None:
            self.bt = bt_state() if have("bluetoothctl") else {"on": False, "devices": []}
        if have("bluetoothctl") and not self.bt["on"]:
            run(["rfkill", "unblock", "bluetooth"])
            run(["bluetoothctl", "power", "on"])
        view = self.radar_view("Looking for devices", "Put the device in pairing mode · click it to pair · Backspace: back · Esc closes",
                               self.bt_radar_items)
        if have("bluetoothctl"):
            self.scan_proc = subprocess.Popen(["bluetoothctl", "--timeout", "60", "scan", "on"],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.refresh_every(1500, self.radar_poll)
        return view

    def radar_poll(self):
        if getattr(self, "bt_loading", False):
            return
        self.bt_loading = True
        in_thread(bt_state, self.radar_bt_update)

    def radar_bt_update(self, st):
        self.bt_loading = False
        if st is not None and not self.busy:
            self.bt = st

    def bt_radar_items(self):
        out = []
        for d in [d for d in (self.bt or {}).get("devices", []) if not d["paired"]][:12]:
            rssi = d["rssi"] if d["rssi"] is not None else -85
            strength = max(0.05, min(1.0, (rssi + 100) / 60))
            out.append({"key": d["mac"], "strength": strength, "glyph": G[d["icon"]], "label": d["name"],
                        "action": lambda d=d: self.bt_do("pair", d)})
        return out

    def stop_scan(self):
        if self.scan_proc and self.scan_proc.poll() is None:
            self.scan_proc.terminate()
            subprocess.Popen(["bluetoothctl", "scan", "off"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.scan_proc = None


def main():
    view = sys.argv[1] if len(sys.argv) > 1 else "wifi"
    if view not in ("wifi", "wifi-radar", "bt", "bt-cards", "bt-radar"):
        print(__doc__, file=sys.stderr)
        return 2
    family = "wifi" if view.startswith("wifi") else "bt"
    if PID_FILE.exists():            # the same menu again closes it; the other one replaces it
        try:
            pid, old = (PID_FILE.read_text().split() + ["", ""])[:2]
            os.kill(int(pid), signal.SIGTERM)
            PID_FILE.unlink(missing_ok=True)
            if old == family:
                return 0
            time.sleep(0.15)
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    PID_FILE.write_text(f"{os.getpid()} {family}")
    win = None
    try:
        win = NetMenu(view)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (Gtk.main_quit(), False)[1])
        Gtk.main()
    finally:
        if win:
            win.stop_scan()
        try:
            if PID_FILE.read_text().split()[0] == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
