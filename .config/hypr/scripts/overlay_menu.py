#!/usr/bin/env python3
"""overlay_menu.py - the small menus, drawn as overlays above everything (like the power menu).

    overlay_menu.py shortcuts    Super + G   glass panel: every shortcut, searchable; Enter runs it
    overlay_menu.py clipboard    Super + V   spotlight: clipboard history with image thumbnails;
                                             Enter copies, Delete removes an entry
    overlay_menu.py screenshot   Super + P   tiles: region, screen, window, pick a window, draw,
                                             record / stop, color picker
    overlay_menu.py power        Super + F12 tiles: performance / balanced / power saver
    overlay_menu.py bartheme     Super + Shift + T  a picture of each bar style on your wallpaper
    overlay_menu.py audio        (recording) pill bar to pick the sound; prints sys / mic / both / none

Esc, a click outside, or the same shortcut again closes it. Colors follow the wallpaper.
GTK 3 on a layer-shell overlay: no window, no border, Hyprland fades it in
(layerrule on the "overlay-menu" namespace in hyprland.hl).
"""

import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk   # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell           # noqa: E402
except (ImportError, ValueError):
    GtkLayerShell = None

HOME = Path.home()
SCRIPTS = Path(__file__).resolve().parent
PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "overlay-menu.pid"
THUMBS = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "cliphist-thumbs"
NERD = '"JetBrainsMono Nerd Font"'


# ------------------------------------------------------------------------------ helpers
def palette():
    c = {"bg": "#141824", "fg": "#eef1f7", "accent": "#7aa2f7"}
    try:
        data = json.loads((HOME / ".cache" / "wal" / "colors.json").read_text(encoding="utf-8"))
        c = {"bg": data["special"]["background"], "fg": data["special"]["foreground"], "accent": data["colors"]["color1"]}
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


def spawn_later(cmd: str, delay=0.18):
    """Run a shell command once the overlay has gone (so it isn't in screenshots or in the way)."""
    subprocess.Popen(["sh", "-c", f"sleep {delay}; {cmd}"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def lab(text="", *classes, xalign=0.0, ellipsize=False, markup=False):
    w = Gtk.Label()
    (w.set_markup if markup else w.set_text)(text)
    w.set_xalign(xalign)
    if ellipsize:
        w.set_ellipsize(3)            # Pango.EllipsizeMode.END
        w.set_max_width_chars(60)
    for c in classes:
        w.get_style_context().add_class(c)
    return w


def keycaps(combo: str):
    box = Gtk.Box(spacing=4)
    box.set_valign(Gtk.Align.CENTER)
    for k in combo.split(" + "):
        box.pack_start(lab(k, "kc"), False, False, 0)
    return box


# ------------------------------------------------------------------------------ the overlay
class Overlay(Gtk.Window):
    def __init__(self, mode):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.mode = mode
        self.set_title("overlay-menu")
        self.set_app_paintable(True)
        screen = self.get_screen()
        if screen.get_rgba_visual():
            self.set_visual(screen.get_rgba_visual())
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
        self.css()
        backdrop = Gtk.EventBox()
        backdrop.get_style_context().add_class("backdrop")
        backdrop.connect("button-press-event", lambda *_: (Gtk.main_quit(), True)[1])
        self.content = Gtk.EventBox()                 # clicks inside don't close
        self.content.connect("button-press-event", lambda *_: True)
        backdrop.add(self.content)
        self.add(backdrop)
        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)
        {"shortcuts": self.build_shortcuts, "clipboard": self.build_clipboard, "screenshot": self.build_screenshot,
         "power": self.build_power, "bartheme": self.build_bartheme, "audio": self.build_audio}[mode]()

    def css(self):
        p = palette()
        a, b, f, k = p["accent"], p["bg"], p["fg"], ink(p["accent"])
        css = f"""
        * {{ font-family: "Inter", {NERD}, sans-serif; color: {f}; outline-style: none; outline-width: 0;
             text-shadow: none; -gtk-icon-shadow: none; }}
        window {{ background: transparent; }}
        .backdrop {{ background: rgba(0,0,0,0.30); }}
        .glyph {{ font-family: {NERD}; }}
        entry {{ background: {rgba(f, .08)}; border: none; box-shadow: none; border-radius: 99px;
                 padding: 8px 16px; caret-color: {a}; font-size: 14px; min-height: 22px; }}
        entry selection {{ background: {rgba(a, .45)}; }}
        list, viewport, scrolledwindow {{ background: transparent; border: none; }}
        scrolledwindow undershoot, scrolledwindow overshoot {{ background: none; }}
        row {{ background: transparent; border-radius: 14px; padding: 6px 10px; margin: 1px 0; }}
        row:hover {{ background: {rgba(f, .06)}; }}
        .sub {{ color: {rgba(f, .55)}; font-size: 11px; }}
        .section {{ font-size: 10.5px; font-weight: 700; letter-spacing: 1px; color: {rgba(f, .5)}; margin: 12px 10px 4px; }}
        .kc {{ background: {rgba(f, .10)}; border: 1px solid {rgba(f, .16)}; border-bottom-width: 2px; border-radius: 6px;
               padding: 1px 7px; font-family: {NERD}; font-size: 11px; font-weight: 700; color: {rgba(f, .82)}; }}
        .empty {{ color: {rgba(f, .5)}; padding: 24px; }}

        /* Glass panel (shortcuts) */
        .panel {{ background: {rgba(b, .84)}; border: 1px solid {rgba(f, .14)}; border-radius: 26px; padding: 22px; }}
        .badge {{ background: {a}; border-radius: 13px; min-width: 42px; min-height: 42px; font-family: {NERD}; font-size: 20px; color: {k}; }}
        .title {{ font-size: 19px; font-weight: 700; }}
        .roundicon {{ background: {rgba(f, .08)}; border-radius: 99px; min-width: 34px; min-height: 34px;
                      font-family: {NERD}; font-size: 15px; color: {a}; }}
        .panel row:selected {{ background: {rgba(a, .22)}; box-shadow: inset 0 0 0 1px {rgba(a, .6)}; }}

        /* Spotlight (clipboard) */
        .bar {{ background: {rgba(b, .90)}; border: 1px solid {rgba(f, .16)}; border-radius: 18px; padding: 10px 14px; }}
        .bar entry {{ background: transparent; font-size: 18px; padding: 6px 4px; }}
        .bar .glyph {{ color: {a}; font-size: 20px; }}
        .results {{ background: {rgba(b, .86)}; border: 1px solid {rgba(f, .10)}; border-radius: 18px; padding: 6px; }}
        .results row:selected {{ background: {a}; }}
        .results row:selected label {{ color: {k}; }}
        .results .glyph {{ color: {a}; font-size: 16px; }}
        .thumb {{ border-radius: 6px; }}

        /* Tiles (screenshot) */
        .big-title {{ font-size: 22px; font-weight: 700; }}
        flowbox, flowboxchild {{ background: transparent; padding: 0; }}
        .tile {{ background: {rgba(b, .78)}; border: 1px solid {rgba(f, .12)}; border-radius: 22px; padding: 20px 12px 16px;
                 min-width: 132px; }}
        .tile:hover {{ background: {rgba(b, .9)}; border-color: {rgba(a, .6)}; }}
        flowboxchild:selected .tile {{ background: {a}; border-color: {a}; }}
        flowboxchild:selected .tile label {{ color: {k}; }}
        .tile-icon {{ font-family: {NERD}; font-size: 34px; color: {a}; }}
        .tile-name {{ font-weight: 700; font-size: 13px; }}
        .tile-key {{ font-size: 11px; color: {rgba(f, .6)}; }}
        .hint {{ color: {rgba(f, .65)}; font-size: 12px; }}

        /* Bar theme pictures */
        .barcard {{ border-radius: 16px; padding: 6px; background: {rgba(b, .55)}; border: 1px solid {rgba(f, .10)}; }}
        flowboxchild:selected .barcard {{ background: {rgba(a, .25)}; border: 2px solid {a}; }}
        .barname {{ font-weight: 700; font-size: 13px; }}
        flowboxchild:selected .barname {{ color: {a}; }}

        /* Pill bar (recording sound) */
        .pillbar {{ background: {rgba(b, .92)}; border: 1px solid {rgba(f, .14)}; border-radius: 99px; padding: 8px 8px 8px 18px; }}
        .pillbar .glyph {{ color: #e5484d; font-size: 18px; }}
        button {{ background: none; background-image: none; border: none; box-shadow: none; text-shadow: none; }}
        .pill {{ background: {rgba(f, .10)}; border-radius: 99px; padding: 6px 14px; }}
        .pill:hover {{ background: {rgba(f, .18)}; }}
        .pill.on {{ background: {a}; }}
        .pill.on label {{ color: {k}; }}
        .recbtn {{ background: #e5484d; border-radius: 99px; min-width: 40px; min-height: 40px; padding: 0; margin-left: 4px; }}
        .recbtn:hover {{ background: #ff6166; }}
        .recbtn label {{ color: #ffffff; font-family: {NERD}; font-size: 16px; }}
        """
        prov = Gtk.CssProvider()
        prov.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # -------------------------------------------------------------- keyboard
    def on_key(self, _w, e):
        k = e.keyval
        if k == Gdk.KEY_Escape:
            Gtk.main_quit()
            return True
        if self.mode == "audio":
            if k in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
                step = -1 if k in (Gdk.KEY_Left, Gdk.KEY_ISO_Left_Tab) else 1
                self.pick_audio((self.audio_sel + step) % len(self.audio_opts))
            elif Gdk.KEY_1 <= k <= Gdk.KEY_4:
                self.pick_audio(k - Gdk.KEY_1)
                self.start_recording()
            elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
                self.start_recording()
            return True
        if self.mode in ("screenshot", "power", "bartheme"):
            if Gdk.KEY_1 <= k <= Gdk.KEY_9:
                i = k - Gdk.KEY_1
                if i < len(self.tile_actions):
                    self.tile_actions[i]()
                return True
            # Arrows and Enter handled here: the keyboard focus can't be relied on to be in the grid
            n = len(self.tile_actions)
            sel = self.flow.get_selected_children()
            i = sel[0].get_index() if sel else 0
            moves = {Gdk.KEY_Left: -1, Gdk.KEY_Right: 1, Gdk.KEY_Up: -self.tile_cols, Gdk.KEY_Down: self.tile_cols,
                     Gdk.KEY_h: -1, Gdk.KEY_l: 1, Gdk.KEY_k: -self.tile_cols, Gdk.KEY_j: self.tile_cols,
                     Gdk.KEY_Tab: 1, Gdk.KEY_ISO_Left_Tab: -1}
            if k in moves:
                j = i + moves[k]
                if k in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
                    j %= n
                if 0 <= j < n:
                    child = self.flow.get_child_at_index(j)
                    self.flow.select_child(child)
                    child.grab_focus()
                return True
            if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
                self.tile_actions[i]()
                return True
            return False
        if k in (Gdk.KEY_Down, Gdk.KEY_Up, Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
            step = {Gdk.KEY_Down: 1, Gdk.KEY_Up: -1, Gdk.KEY_Page_Down: 6, Gdk.KEY_Page_Up: -6}[k]
            self.move(step)
            return True
        if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            row = self.listbox.get_selected_row()
            if row:
                self.activate(row)
            return True
        if self.mode == "clipboard" and k == Gdk.KEY_Delete:
            self.delete_selected()
            return True
        return False

    def visible_rows(self):
        return [r for r in self.listbox.get_children() if r.get_child_visible()]

    def move(self, step):
        rows = self.visible_rows()
        if not rows:
            return
        cur = self.listbox.get_selected_row()
        i = rows.index(cur) if cur in rows else -1
        i = max(0, min(len(rows) - 1, i + step))
        self.listbox.select_row(rows[i])
        rows[i].grab_focus()
        self.entry.grab_focus_without_selecting()

    def select_first(self):
        rows = self.visible_rows()
        if rows:
            self.listbox.select_row(rows[0])

    def search_box(self, placeholder):
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(placeholder)
        self.entry.connect("changed", lambda *_: (self.listbox.invalidate_filter(), self.listbox.invalidate_headers(),
                                                  self.select_first()))
        return self.entry

    # -------------------------------------------------------------- Shortcuts: glass panel
    def build_shortcuts(self):
        sys.path.insert(0, str(SCRIPTS))
        import settings as st                         # its shortcut parser (also used by Settings)
        GLib.set_prgname("overlay-menu")              # importing it renamed this program
        try:
            binds = st.parse_binds((HOME / ".config" / "hypr" / "hyprland.hl").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            binds = []
        overrides, names = st.read_overrides(), st.cheatsheet_descriptions()
        icons = {"Apps and menus": "\U000f003b", "Windows": "\U000f05b0", "Workspaces": "\U000f0570"}
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        panel.get_style_context().add_class("panel")
        panel.set_size_request(640, -1)
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.CENTER)
        head = Gtk.Box(spacing=12)
        head.pack_start(lab("\U000f030c", "badge", xalign=0.5), False, False, 0)
        head.pack_start(lab("Shortcuts", "title"), False, False, 0)
        head.pack_end(lab("Enter runs it · Esc closes", "sub"), False, False, 0)
        panel.pack_start(head, False, False, 0)
        panel.pack_start(self.search_box("Search a shortcut"), False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", lambda _l, r: self.activate(r))
        for title in ("Apps and menus", "Windows", "Workspaces"):
            for b in [b for b in binds if st.bind_group(b) == title]:
                mods, key = overrides.get(st.combo_id(b["mods"], b["key"]), (b["mods"], b["key"]))
                combo = st.combo_label(mods, key)
                text = st.describe(b, names)
                row = Gtk.ListBoxRow()
                row.group, row.bind, row.search = title, b, f"{text} {combo} {title}".lower()
                box = Gtk.Box(spacing=12)
                box.pack_start(lab(icons.get(title, "\U000f030c"), "roundicon", xalign=0.5), False, False, 0)
                box.pack_start(lab(text, ellipsize=True), True, True, 0)
                box.pack_end(keycaps(combo), False, False, 0)
                row.add(box)
                self.listbox.add(row)
        self.listbox.set_filter_func(lambda r: self.entry.get_text().lower().strip() in r.search)
        self.listbox.set_header_func(self.group_header)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(420)
        scroll.set_max_content_height(560)
        scroll.set_propagate_natural_height(True)
        scroll.add(self.listbox)
        panel.pack_start(scroll, True, True, 0)
        self.content.add(panel)
        self.select_first()

    def group_header(self, row, before):
        if before is None or before.group != row.group:
            row.set_header(lab(row.group.upper(), "section"))
        else:
            row.set_header(None)

    # -------------------------------------------------------------- Clipboard: spotlight
    def build_clipboard(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_size_request(680, -1)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_valign(Gtk.Align.START)
        outer.set_margin_top(int(Gdk.Screen.get_default().get_height() * 0.16) if Gdk.Screen.get_default() else 160)
        bar = Gtk.Box(spacing=10)
        bar.get_style_context().add_class("bar")
        bar.pack_start(lab("\U000f0147", "glyph"), False, False, 0)
        bar.pack_start(self.search_box("Search the clipboard"), True, True, 0)
        bar.pack_end(lab("Enter copies · Del removes", "sub"), False, False, 0)
        outer.pack_start(bar, False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.connect("row-activated", lambda _l, r: self.activate(r))
        self.listbox.set_filter_func(lambda r: self.entry.get_text().lower().strip() in r.search)
        self.results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.results.get_style_context().add_class("results")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_max_content_height(470)
        scroll.set_propagate_natural_height(True)
        scroll.add(self.listbox)
        self.results.pack_start(scroll, True, True, 0)
        self.empty = lab("", "empty", xalign=0.5)
        self.empty.set_no_show_all(True)             # shown only when there is nothing to list
        self.results.pack_start(self.empty, False, False, 0)
        outer.pack_start(self.results, False, False, 0)
        self.content.add(outer)
        # The list itself takes milliseconds: read it now, so the menu opens already filled;
        # only the image thumbnails come a moment later
        entries, error = self.read_clipboard()
        self.fill_clipboard(entries, error)
        if entries:
            threading.Thread(target=self.load_thumbs, args=(entries,), daemon=True).start()

    @staticmethod
    def read_clipboard():
        """cliphist's list, read as bytes: it shortens long entries and can cut a character in
        half, so each line keeps its original bytes (for copying / deleting) next to a text
        version for display. Returns (entries, error message or None)."""
        try:
            raw = subprocess.run(["cliphist", "list"], capture_output=True, timeout=5).stdout
        except FileNotFoundError:
            return [], "cliphist is not installed (sudo apt install cliphist)"
        except subprocess.TimeoutExpired:
            return [], "The clipboard history did not answer"
        except Exception as e:
            return [], f"Could not read the clipboard: {e}"
        entries = []
        for line in raw.split(b"\n"):
            if b"\t" in line:
                entries.append((line, line.decode("utf-8", errors="replace")))
            if len(entries) >= 200:
                break
        return entries, None

    def load_thumbs(self, entries):
        THUMBS.mkdir(parents=True, exist_ok=True)
        for line, text in entries[:60]:               # thumbnails for the recent images
            try:
                ident, content = text.split("\t", 1)
                if not content.startswith("[[ binary data"):
                    continue
                thumb = THUMBS / f"{ident}.img"
                if not thumb.exists():
                    with open(thumb, "wb") as f:
                        subprocess.run(["cliphist", "decode"], input=line, stdout=f, timeout=5)
                GLib.idle_add(self.set_thumb, ident, str(thumb))
            except Exception as e:
                sys.stderr.write(f"overlay_menu: thumbnail: {e!r}\n")

    def fill_clipboard(self, entries, error=None):
        self.thumb_widgets = {}
        for line, decoded in entries:
            try:
                ident, content = decoded.split("\t", 1)
                image = content.startswith("[[ binary data")
                text = content.strip()
                link = text.startswith(("http://", "https://"))
                row = Gtk.ListBoxRow()
                row.line, row.ident = line, ident
                row.search = ("image " if image else "") + text.lower()
                box = Gtk.Box(spacing=12)
                if image:
                    img = Gtk.Image.new_from_icon_name("image-x-generic", Gtk.IconSize.DND)
                    img.get_style_context().add_class("thumb")
                    self.thumb_widgets[ident] = img
                    box.pack_start(img, False, False, 0)
                    info = text.strip("[] ").replace("binary data", "").strip()
                    title, sub = "Image", info
                else:
                    box.pack_start(lab("\U000f0337" if link else "\U000f09a8", "glyph", xalign=0.5), False, False, 0)
                    title, sub = " ".join(text.split())[:140], ("Link" if link else "Text")
                texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                texts.set_valign(Gtk.Align.CENTER)
                texts.pack_start(lab(title, ellipsize=True), False, False, 0)
                texts.pack_start(lab(sub, "sub", ellipsize=True), False, False, 0)
                box.pack_start(texts, True, True, 0)
                row.add(box)
                self.listbox.add(row)
            except Exception as e:                    # one odd entry must not stop the list
                sys.stderr.write(f"overlay_menu: entry skipped: {e!r}\n")
        self.listbox.show_all()
        self.empty.set_text(error or "The clipboard is empty")
        self.empty.set_visible(not entries)
        self.select_first()
        return False

    def set_thumb(self, ident, path):
        img = self.thumb_widgets.get(ident)
        if img:
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 64, 40, True)
                img.set_from_pixbuf(pix)
            except Exception:
                pass
        return False

    def delete_selected(self):
        row = self.listbox.get_selected_row()
        if not row:
            return
        subprocess.run(["cliphist", "delete"], input=row.line, timeout=5)
        rows = self.visible_rows()
        i = rows.index(row)
        self.listbox.remove(row)
        rows = self.visible_rows()
        if rows:
            self.listbox.select_row(rows[min(i, len(rows) - 1)])
        self.empty.set_visible(not rows)

    # -------------------------------------------------------------- Screenshot: tiles
    def build_screenshot(self):
        recording = subprocess.run(["pgrep", "-x", "wf-recorder"], capture_output=True).returncode == 0 or \
            subprocess.run(["pgrep", "-x", "wl-screenrec"], capture_output=True).returncode == 0
        self.actions = [
            ("\U000f0100", "Region", "Super + Shift + P", "region"),
            ("\U000f0379", "Screen", "Super + Alt + P", "full"),
            ("\U000f05b0", "Window", "the active one", "window"),
            ("\U000f0489", "Pick a window", "click it", "window-select"),
            ("\U000f03eb", "Draw", "Super + Ctrl + P", "swappy"),
            ("\U000f04db" if recording else "\U000f044a", "Stop recording" if recording else "Record",
             "Super + Shift + R", "record"),
            ("\U000f0236", "Color picker", "copies the hex", "color"),
        ]
        tiles = []
        for icon, name, key, mode in self.actions:
            tiles.append((icon, name, key, lambda m=mode: self.run_screenshot(m)))
        self.tile_grid("Screenshot", tiles, 4, 0, "Arrows and Enter, a number, or a click · Esc closes")

    def run_screenshot(self, mode):
        Gtk.main_quit()
        spawn_later(f"{shlex.quote(str(SCRIPTS / 'screenshot.sh'))} {mode}", 0.25)

    def tile_grid(self, title, tiles, cols, selected, hint, widget=None):
        """Big tiles (icon, name, small text, action) or custom widgets, arrows/Enter/number keys."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.pack_start(lab(title, "big-title", xalign=0.5), False, False, 0)
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flow.set_min_children_per_line(cols)
        self.flow.set_max_children_per_line(cols)
        self.flow.set_homogeneous(True)
        self.flow.set_row_spacing(12)
        self.flow.set_column_spacing(12)
        self.flow.set_activate_on_single_click(True)
        self.tile_actions = []
        self.tile_cols = cols
        for i, t in enumerate(tiles):
            if widget:
                child, action = widget(i, t), t[-1]
            else:
                icon, name, small, action = t
                child = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                child.get_style_context().add_class("tile")
                child.pack_start(lab(icon, "tile-icon", xalign=0.5), False, False, 0)
                child.pack_start(lab(name, "tile-name", xalign=0.5), False, False, 0)
                child.pack_start(lab(f"{i + 1} · {small}", "tile-key", xalign=0.5), False, False, 0)
            self.flow.add(child)
            self.tile_actions.append(action)
        self.flow.connect("child-activated", lambda _f, c: self.tile_actions[c.get_index()]())
        box.pack_start(self.flow, False, False, 0)
        if hint:
            box.pack_start(lab(hint, "hint", xalign=0.5), False, False, 0)
        self.content.add(box)
        chosen = self.flow.get_child_at_index(max(0, min(selected, len(tiles) - 1)))
        self.flow.select_child(chosen)
        GLib.idle_add(lambda: (chosen.grab_focus(), False)[1])

    # -------------------------------------------------------------- Power profile: tiles
    def build_power(self):
        current = subprocess.run([str(SCRIPTS / "power-mode.sh"), "get"], capture_output=True, text=True).stdout.strip()
        profiles = [("\U000f04c5", "Performance", "Fastest, more fan", "performance"),
                    ("\U000f0f86", "Balanced", "The default", "balanced"),
                    ("\U000f032a", "Power saver", "Longest battery", "power-saver")]

        def choose(prof):
            Gtk.main_quit()
            spawn_later(f"{shlex.quote(str(SCRIPTS / 'power-mode.sh'))} {prof}", 0.05)
        tiles = [(i, n, d + (" · now" if p == current else ""), lambda p=p: choose(p)) for i, n, d, p in profiles]
        sel = next((k for k, t in enumerate(profiles) if t[3] == current), 1)
        self.tile_grid("Power profile", tiles, 3, sel, self.battery_line())

    @staticmethod
    def battery_line():
        for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
            try:
                cap = int((bat / "capacity").read_text())
                status = (bat / "status").read_text().strip().lower()
            except (OSError, ValueError):
                continue
            text = f"Battery {cap}% · {status}"
            try:
                out = subprocess.run(["upower", "-i", f"/org/freedesktop/UPower/devices/battery_{bat.name}"],
                                     capture_output=True, text=True, timeout=2).stdout
                for line in out.splitlines():
                    if "time to" in line:
                        text += " · " + line.split(":", 1)[1].strip() + (" left" if "empty" in line else " to full")
                        break
            except (OSError, subprocess.TimeoutExpired):
                pass
            return text
        return "Arrows and Enter, or 1-3 · Esc closes"

    # -------------------------------------------------------------- Bar theme: pictures
    def build_bartheme(self):
        sys.path.insert(0, str(SCRIPTS))
        import settings as st                         # its bar preview drawing
        GLib.set_prgname("overlay-menu")
        layout = HOME / ".config" / "waybar" / "scripts" / "layout.py"
        parts = subprocess.run(["python3", str(layout), "--get"], capture_output=True, text=True).stdout.split()
        current, pos = (parts + ["capsule", "top"])[:2]
        themes = ["default", "line", "zen", "experimental", "capsule", "powerline", "dock", "island"]
        try:                                          # one small copy of the wallpaper for all eight
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(os.path.realpath(st.WALLPAPERS / "current.jpg"), 480, 270, True)
        except Exception:
            pix = None
        real = st.WALLPAPERS
        st.WALLPAPERS = Path("/nonexistent")          # skip each preview's own (slow) load

        def card(i, t):
            theme = t[0]
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            v.get_style_context().add_class("barcard")
            area = st.Settings.bar_preview(None, "top" if theme == "island" else pos, theme)
            area.pix = pix
            area.set_size_request(236, 132)
            v.pack_start(area, False, False, 0)
            v.pack_start(lab(theme.capitalize() + ("  · now" if theme == current else ""), "barname", xalign=0.5), False, False, 4)
            return v

        def choose(theme):
            Gtk.main_quit()
            spawn_later(f"{shlex.quote(str(HOME / '.config/waybar/scripts/select.sh'))} {theme}", 0.05)
        tiles = [(t, lambda t=t: choose(t)) for t in themes]
        self.tile_grid("Bar theme", tiles, 4, themes.index(current) if current in themes else 0,
                       "Position, size and gap: Settings → Appearance → Waybar", widget=card)
        st.WALLPAPERS = real

    # -------------------------------------------------------------- Recording sound: pill bar
    AUDIO_CHOICE = HOME / ".cache" / "record-audio-choice"

    def build_audio(self):
        self.audio_opts = [("sys", "\U000f04c3", "System sound"), ("mic", "\U000f036c", "Microphone"),
                           ("both", "\U000f04c3 \U000f036c", "Both"), ("none", "\U000f075f", "No sound")]
        try:
            last = self.AUDIO_CHOICE.read_text().strip()
        except OSError:
            last = "sys"
        self.audio_sel = next((i for i, o in enumerate(self.audio_opts) if o[0] == last), 0)
        bar = Gtk.Box(spacing=8)
        bar.get_style_context().add_class("pillbar")
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.START)
        screen = Gdk.Screen.get_default()
        bar.set_margin_top(int(screen.get_height() * 0.08) if screen else 80)
        bar.pack_start(lab("\U000f044a", "glyph"), False, False, 0)
        bar.pack_start(lab("Sound", "tile-name"), False, False, 6)
        self.pills = []
        for i, (_k, icon, name) in enumerate(self.audio_opts):
            b = Gtk.Button()
            b.set_can_focus(False)
            inner = Gtk.Box(spacing=6)
            inner.pack_start(lab(icon, "glyph-plain"), False, False, 0)
            inner.pack_start(lab(name), False, False, 0)
            b.add(inner)
            b.get_style_context().add_class("pill")
            b.connect("clicked", lambda _b, i=i: self.pick_audio(i))
            bar.pack_start(b, False, False, 0)
            self.pills.append(b)
        rec = Gtk.Button(label="\U000f044a")
        rec.set_can_focus(False)
        rec.set_tooltip_text("Start recording (Enter)")
        rec.get_style_context().add_class("recbtn")
        rec.connect("clicked", lambda *_: self.start_recording())
        bar.pack_start(rec, False, False, 0)
        self.content.add(bar)
        self.pick_audio(self.audio_sel)

    def pick_audio(self, i):
        self.audio_sel = i
        for k, b in enumerate(self.pills):
            ctx = b.get_style_context()
            (ctx.add_class if k == i else ctx.remove_class)("on")

    def start_recording(self):
        key = self.audio_opts[self.audio_sel][0]
        try:
            self.AUDIO_CHOICE.parent.mkdir(parents=True, exist_ok=True)
            self.AUDIO_CHOICE.write_text(key + "\n")
        except OSError:
            pass
        print(key, flush=True)
        Gtk.main_quit()

    # -------------------------------------------------------------- activation
    def activate(self, row):
        if self.mode == "shortcuts":
            b = row.bind
            Gtk.main_quit()
            cmd = ["hyprctl", "dispatch", b["dispatcher"]] + ([b["args"]] if b.get("args") else [])
            spawn_later(" ".join(shlex.quote(x) for x in cmd))
        elif self.mode == "clipboard":
            line = row.line
            Gtk.main_quit()
            p = subprocess.run(["cliphist", "decode"], input=line, capture_output=True, timeout=5)
            if p.returncode == 0:
                subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, start_new_session=True).communicate(p.stdout)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "shortcuts"
    if mode not in ("shortcuts", "clipboard", "screenshot", "power", "bartheme", "audio"):
        print(__doc__, file=sys.stderr)
        return 2
    # The same shortcut again closes it (any menu: one at a time)
    if PID_FILE.exists():
        try:
            os.kill(int(PID_FILE.read_text().strip()), signal.SIGTERM)
            PID_FILE.unlink(missing_ok=True)
            return 0
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    try:
        win = Overlay(mode)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (Gtk.main_quit(), False)[1])
        win.show_all()
        if mode in ("shortcuts", "clipboard"):
            win.entry.grab_focus()
        Gtk.main()
    finally:
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
