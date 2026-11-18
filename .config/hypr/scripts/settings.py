#!/usr/bin/env python3
"""settings.py - Settings window (Super + H).

Categories on the left (with search), tabs, live previews and real controls on the right.
Every control calls the same scripts the Rofi menu (quick-settings.sh) uses, so behaviour
is identical; changes apply immediately. Colors follow the pywal palette, live.

    Ctrl+F or just type: search      Esc: close      Super + H again: close
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango
except (ImportError, ValueError) as e:
    sys.stderr.write(f"settings: GTK3 unavailable: {e}\n")
    sys.exit(1)

GLib.set_prgname("dotfiles-settings")          # Wayland app id, used by the Hyprland window rule

HOME = Path.home()
HYPR = HOME / ".config" / "hypr"
SCRIPTS = HYPR / "scripts"
WAYBAR = HOME / ".config" / "waybar" / "scripts"
WALLPAPERS = HOME / "Pictures" / "wallpapers"
USER_SETTINGS = HYPR / "user-settings.hl"
USER_APPS = HYPR / "user-apps.hl"
PID_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "dotfiles-settings.pid"


# ------------------------------------------------------------------------------ helpers
def run(cmd, timeout=4.0) -> str:
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def spawn(cmd):
    try:
        subprocess.Popen(cmd, shell=isinstance(cmd, str), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        sys.stderr.write(f"settings: {cmd}: {e}\n")


def have(cmd) -> bool:
    return shutil.which(cmd) is not None


def in_background(work, then):
    """Run work() in a thread, then then(result) on the GTK main loop."""
    def go():
        try:
            result = work()
        except Exception as e:
            sys.stderr.write(f"settings: {e}\n")
            result = None
        GLib.idle_add(lambda: (then(result), False)[1])
    threading.Thread(target=go, daemon=True).start()


def notify(msg):
    spawn(["notify-send", "-u", "low", "-h", "string:x-canonical-private-synchronous:sys-notify", "Settings", msg])


def set_block(name: str, content: str):
    """Replace (or add) a marked block in user-settings.hl (same markers as quick-settings.sh)."""
    begin, end = f"# >>> quick-settings: {name}", f"# <<< quick-settings: {name}"
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
    out += [begin, content, end]
    USER_SETTINGS.write_text("\n".join(out) + "\n", encoding="utf-8")


def set_app_var(name: str, value: str):
    """$terminal / $fileManager live in user-apps.hl (sourced before the keybinds)."""
    pat = re.compile(rf"^\s*\${name}\s*=")
    for f in (USER_APPS, USER_SETTINGS):
        try:
            kept = [l for l in f.read_text(encoding="utf-8", errors="replace").splitlines() if not pat.match(l)]
            f.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        except OSError:
            pass
    with open(USER_APPS, "a") as f:
        f.write(f"${name} = {value}\n")


def read_app_var(name: str, default: str) -> str:
    try:
        for line in reversed(USER_APPS.read_text(encoding="utf-8", errors="replace").splitlines()):
            m = re.match(rf"^\s*\${name}\s*=\s*(\S+)", line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return default


# ------------------------------------------------------------------------------ shortcuts
USER_BINDS = HYPR / "user-binds.hl"
MOD_ORDER = ["SUPER", "CTRL", "ALT", "SHIFT"]
MOD_ALIASES = {"SUPER": "SUPER", "WIN": "SUPER", "LOGO": "SUPER", "MOD4": "SUPER", "CTRL": "CTRL", "CONTROL": "CTRL",
               "ALT": "ALT", "MOD1": "ALT", "SHIFT": "SHIFT"}
KEY_LABELS = {"ampersand": "&", "eacute": "é", "quotedbl": '"', "apostrophe": "'", "parenleft": "(", "parenright": ")",
              "minus": "-", "egrave": "è", "underscore": "_", "ccedilla": "ç", "agrave": "à", "escape": "Esc",
              "return": "Return", "print": "Print", "left": "←", "right": "→", "up": "↑", "down": "↓", "space": "Space",
              "tab": "Tab", "comma": ",", "semicolon": ";", "colon": ":", "exclam": "!", "dollar": "$", "asterisk": "*"}


def norm_mods(text: str, main_mod: str = "SUPER") -> str:
    words = text.replace("$mainMod", main_mod).replace("_", " ").upper().split()
    found = {MOD_ALIASES[w] for w in words if w in MOD_ALIASES}
    return " ".join(m for m in MOD_ORDER if m in found)


def combo_label(mods: str, key: str) -> str:
    k = KEY_LABELS.get(key.lower(), key.upper() if len(key) == 1 else key)
    return " + ".join([m.capitalize() if m != "CTRL" else "Ctrl" for m in mods.split()] + [k])


def combo_id(mods: str, key: str) -> str:
    return f"{mods}|{key.lower()}"


def parse_binds(text: str) -> list:
    """bind/binde/... lines of hyprland.hl outside submaps, with $mainMod resolved."""
    main_mod = "SUPER"
    m = re.search(r"^\$mainMod\s*=\s*(\S+)", text, re.M)
    if m:
        main_mod = norm_mods(m.group(1)) or "SUPER"
    binds, submap = [], "reset"
    for line in text.splitlines():
        s = line.strip()
        sm = re.match(r"^submap\s*=\s*(\S+)", s)
        if sm:
            submap = sm.group(1)
            continue
        bm = re.match(r"^(bind[a-z]*)\s*=\s*(.*)$", s)
        if not bm or submap != "reset":
            continue
        parts = [p.strip() for p in bm.group(2).split(",", 3)]
        if len(parts) < 3 or parts[1].lower().startswith("mouse"):
            continue
        binds.append({"type": bm.group(1), "mods": norm_mods(parts[0], main_mod), "key": parts[1],
                      "dispatcher": parts[2], "args": parts[3] if len(parts) > 3 else ""})
    return binds


def read_overrides() -> dict:
    """{original combo id: (new mods, new key)} from user-binds.hl."""
    out = {}
    try:
        text = USER_BINDS.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for m in re.finditer(r"^# >>> settings: (.+?)\n(.*?)^# <<< settings: \1$", text, re.M | re.S):
        bind = re.search(r"^bind[a-z]*\s*=\s*([^,]*),\s*([^,]+),", m.group(2), re.M)
        if bind:
            out[m.group(1)] = (norm_mods(bind.group(1)), bind.group(2).strip())
    return out


def write_override(bind: dict, new_mods: str, new_key: str):
    """Rebind `bind` to new_mods + new_key (or drop the override when it's the original keys)."""
    ident = combo_id(bind["mods"], bind["key"])
    try:
        text = USER_BINDS.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = "# Shortcuts changed in Settings (Super + H -> Shortcuts). Managed by settings.py.\n"
    text = re.sub(rf"^# >>> settings: {re.escape(ident)}\n.*?^# <<< settings: {re.escape(ident)}\n?", "",
                  text, flags=re.M | re.S)
    if combo_id(new_mods, new_key) != ident:
        args = f", {bind['args']}" if bind["args"] else ","
        text = text.rstrip("\n") + "\n" + "\n".join([
            f"# >>> settings: {ident}",
            f"unbind = {bind['mods']}, {bind['key']}",
            f"{bind['type']} = {new_mods}, {new_key}, {bind['dispatcher']}{args}",
            f"# <<< settings: {ident}"]) + "\n"
    USER_BINDS.write_text(text, encoding="utf-8")


def reset_overrides():
    USER_BINDS.write_text("# Shortcuts changed in Settings (Super + H -> Shortcuts). Managed by settings.py.\n", encoding="utf-8")


def describe(bind: dict, cheatsheet: dict) -> str:
    known = cheatsheet.get(combo_id(bind["mods"], bind["key"]))
    if known:
        return known
    d, a = bind["dispatcher"], bind["args"]
    if d == "workspace":
        return f"Go to workspace {a}"
    if d == "movetoworkspace":
        return f"Move window to workspace {a}"
    if d in ("movefocus", "movewindow"):
        side = {"l": "left", "r": "right", "u": "up", "d": "down"}.get(a, a)
        return ("Focus " if d == "movefocus" else "Move window ") + side
    if d == "resizeactive":
        return f"Resize window ({a})"
    if d == "exec":
        script = re.search(r"([\w-]+)\.(?:sh|py)\b(.*)", a)
        if script:
            name = script.group(1).replace("-", " ").capitalize()
            extra = script.group(2).strip()
            return f"{name} ({extra})" if extra else name
        return a.split()[0] if a else "Run a command"
    return {"killactive": "Close window", "exit": "Exit Hyprland", "togglespecialworkspace": "Scratchpad",
            "togglefloating": "Toggle floating", "fullscreen": "Fullscreen", "layoutmsg": f"Layout: {a}"}.get(d, f"{d} {a}".strip())


def cheatsheet_descriptions() -> dict:
    """Descriptions from keybinds.sh ("icon  SUPER + Q   󰄾  Launcher") by combo."""
    out = {}
    try:
        text = (SCRIPTS / "keybinds.sh").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for m in re.finditer(r'^\s*"(.+?)"\s*$', text, re.M):
        parts = [p.strip() for p in m.group(1).split("\U000f013e")]
        if len(parts) != 2:
            continue
        keys = [k.strip() for k in re.sub(r"^\S+\s+", "", parts[0]).split("+")]
        if not keys:
            continue
        mods = norm_mods(" ".join(keys[:-1]))
        out[combo_id(mods, keys[-1])] = parts[1]
    return out


def bind_group(bind: dict) -> str:
    if bind["dispatcher"] in ("workspace", "movetoworkspace", "togglespecialworkspace"):
        return "Workspaces"
    if bind["dispatcher"] in ("movefocus", "movewindow", "resizeactive", "layoutmsg", "killactive",
                              "togglefloating", "fullscreen", "pseudo"):
        return "Windows"
    return "Apps and menus"


# ------------------------------------------------------------------------------ colors
def load_colors() -> dict:
    c = {"bg": "#1f2230", "fg": "#eceaf4", "accent": "#8f86d8"}
    try:
        data = json.loads((HOME / ".cache" / "wal" / "colors.json").read_text(encoding="utf-8", errors="replace"))
        c = {"bg": data["special"]["background"], "fg": data["special"]["foreground"],
             "accent": data["colors"].get("color1") or c["accent"]}
    except Exception:
        pass
    return c


def rgba(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def css_for(c: dict) -> str:
    bg, fg, acc = c["bg"], c["fg"], c["accent"]
    return f"""
    * {{ font-family: "Inter", "JetBrainsMono Nerd Font", sans-serif; color: {fg}; outline-style: none; }}
    window.settings {{ background: {rgba(bg, 0.95)}; border-radius: 18px; }}
    .sidebar {{ background: {rgba(fg, 0.025)}; border-right: 1px solid {rgba(fg, 0.08)}; padding: 22px 14px 14px 14px; }}
    .app-title {{ font-size: 21px; font-weight: 700; margin: 0 0 12px 6px; }}
    entry.search {{
        background: {rgba(fg, 0.06)}; border: 1px solid {rgba(fg, 0.10)}; border-radius: 12px;
        padding: 8px 12px; box-shadow: none; color: {fg}; caret-color: {fg};
    }}
    entry.search:focus {{ border-color: {acc}; }}
    list, row {{ background: transparent; }}
    row.nav {{ border-radius: 12px; padding: 9px 12px; margin: 1px 0; }}
    row.nav:hover {{ background: {rgba(fg, 0.05)}; }}
    row.nav:selected {{ background: {rgba(acc, 0.32)}; }}
    .nav-icon {{ font-family: "JetBrainsMono Nerd Font"; font-size: 15px; min-width: 22px; }}
    .foot {{ color: {rgba(fg, 0.5)}; font-family: "JetBrainsMono Nerd Font"; font-size: 11px; margin: 0 6px; }}
    .header {{ padding: 20px 24px 16px 24px; border-bottom: 1px solid {rgba(fg, 0.08)}; }}
    .header-icon {{ background: {rgba(fg, 0.07)}; border-radius: 12px; min-width: 42px; min-height: 42px;
                    font-family: "JetBrainsMono Nerd Font"; font-size: 18px; }}
    .header-title {{ font-size: 18px; font-weight: 700; }}
    .dim {{ color: {rgba(fg, 0.6)}; }}
    .small {{ font-size: 11.5px; }}
    button {{ background: {rgba(fg, 0.07)}; border: 1px solid {rgba(fg, 0.10)}; border-radius: 10px;
              padding: 6px 14px; box-shadow: none; text-shadow: none; }}
    button:hover {{ background: {rgba(fg, 0.13)}; }}
    button.round {{ border-radius: 99px; min-width: 34px; min-height: 34px; padding: 0; }}
    .tabs {{ padding: 14px 24px 4px 24px; }}
    button.chip {{ border-radius: 99px; padding: 6px 16px; }}
    button.chip:checked {{ background: {acc}; border-color: transparent; font-weight: 600; }}
    .content {{ padding: 10px 24px 18px 24px; }}
    .section {{ color: {rgba(fg, 0.6)}; font-weight: 600; font-size: 12px; margin: 10px 2px 2px 2px; }}
    .group {{ background: {rgba(fg, 0.04)}; border: 1px solid {rgba(fg, 0.08)}; border-radius: 14px; }}
    .row {{ padding: 11px 14px; min-height: 30px; }}
    .row-sep {{ border-top: 1px solid {rgba(fg, 0.08)}; }}
    .row-title {{ font-weight: 600; }}
    .seg {{ border: 1px solid {rgba(fg, 0.10)}; border-radius: 10px; }}
    .seg button {{ border: none; border-radius: 0; background: {rgba(fg, 0.04)}; padding: 6px 12px; }}
    .seg button:first-child {{ border-radius: 10px 0 0 10px; }}
    .seg button:last-child {{ border-radius: 0 10px 10px 0; }}
    .seg button:checked {{ background: {rgba(acc, 0.65)}; font-weight: 600; }}
    switch {{ background: {rgba(fg, 0.18)}; border: none; border-radius: 99px; }}
    switch:checked {{ background: {acc}; }}
    switch slider {{ background: #ffffff; border: none; border-radius: 99px; box-shadow: none; min-width: 20px; min-height: 20px; }}
    scale trough {{ background: {rgba(fg, 0.18)}; border-radius: 99px; min-height: 6px; border: none; }}
    scale highlight {{ background: {acc}; border-radius: 99px; border: none; }}
    scale slider {{ background: {fg}; border-radius: 99px; min-width: 14px; min-height: 14px; border: none; box-shadow: none; }}
    combobox button {{ padding: 4px 10px; }}
    button.card {{ border-radius: 14px; padding: 16px 8px; }}
    button.card:checked {{ background: {rgba(acc, 0.30)}; border-color: {acc}; }}
    .card-title {{ font-weight: 600; }}
    .preview {{ border-radius: 14px; border: 1px solid {rgba(fg, 0.10)}; }}
    .help {{ border-top: 1px solid {rgba(fg, 0.08)}; padding: 11px 24px; color: {rgba(fg, 0.62)}; font-size: 12px; }}
    .ok {{ color: #7fd18b; }}
    scrolledwindow, viewport {{ background: transparent; border: none; }}
    """


# ------------------------------------------------------------------------------ small widgets
def label(text, *classes, xalign=0.0, wrap=False):
    lab = Gtk.Label(label=text, xalign=xalign)
    for c in classes:
        lab.get_style_context().add_class(c)
    if wrap:
        lab.set_line_wrap(True)
        lab.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return lab


def add_class(widget, *classes):
    for c in classes:
        widget.get_style_context().add_class(c)
    return widget


def row(title, subtitle="", control=None):
    box = add_class(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16), "row")
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text.set_valign(Gtk.Align.CENTER)
    text.pack_start(label(title, "row-title"), False, False, 0)
    if subtitle:
        text.pack_start(label(subtitle, "dim", "small", wrap=True), False, False, 0)
    box.pack_start(text, True, True, 0)
    if control is not None:
        control.set_valign(Gtk.Align.CENTER)
        box.pack_end(control, False, False, 0)
    return box


def group(*rows):
    g = add_class(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), "group")
    for i, r in enumerate(rows):
        if i:
            add_class(r, "row-sep")
        g.pack_start(r, False, False, 0)
    return g


def section(text):
    return label(text, "section")


def button(text, on_click):
    b = Gtk.Button(label=text)
    b.set_focus_on_click(False)
    b.connect("clicked", lambda *_: on_click())
    return b


def segmented(options, current, on_change):
    """options: [(value, label)]; a row of toggle buttons where exactly one is active."""
    box = add_class(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), "seg")
    buttons = []
    state = {"busy": False}

    def toggled(btn, value):
        if state["busy"]:
            return
        state["busy"] = True
        for b in buttons:
            b.set_active(b is btn)
        state["busy"] = False
        on_change(value)

    for value, text in options:
        b = Gtk.ToggleButton(label=text)
        b.set_focus_on_click(False)
        b.set_active(value == current)
        b.connect("toggled", toggled, value)
        buttons.append(b)
        box.pack_start(b, False, False, 0)
    return box


def switch(active, on_change):
    s = Gtk.Switch()
    s.set_active(bool(active))
    s.connect("notify::active", lambda w, _p: on_change(w.get_active()))
    return s


def slider(value, lo, hi, fmt, on_change, step=1, width=220, delay=120):
    """A scale + value label; on_change is called after the knob stops moving for `delay` ms."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
    scale.set_draw_value(False)
    scale.set_size_request(width, -1)
    scale.set_value(value if value is not None else lo)
    val = label(fmt(scale.get_value()), "dim", "small", xalign=1.0)
    val.set_width_chars(6)
    pending = {"id": 0}

    def changed(s):
        val.set_text(fmt(s.get_value()))
        if pending["id"]:
            GLib.source_remove(pending["id"])
        def fire():
            pending["id"] = 0
            on_change(s.get_value())
            return False
        pending["id"] = GLib.timeout_add(delay, fire)

    scale.connect("value-changed", changed)
    box.pack_start(scale, False, False, 0)
    box.pack_start(val, False, False, 0)
    return box


def dropdown(items, current, on_change):
    combo = Gtk.ComboBoxText()
    for value, text in items:
        combo.append(value, text)
    if current is not None:
        combo.set_active_id(current)
    combo.connect("changed", lambda c: c.get_active_id() and on_change(c.get_active_id()))
    return combo


def placeholder(text="Loading…"):
    return group(row(text))


# ------------------------------------------------------------------------------ the window
class Settings(Gtk.Window):
    def __init__(self):
        super().__init__(title="Settings")
        add_class(self, "settings")
        self.set_default_size(1040, 700)
        self.set_app_paintable(True)
        screen = self.get_screen()
        if screen.get_rgba_visual() and screen.is_composited():
            self.set_visual(screen.get_rgba_visual())

        self.colors_mtime = None
        self.css = None
        self.capturing = False
        self.reload_colors()
        GLib.timeout_add(1500, self.reload_colors)

        self.categories = self.define()
        self.current = None
        self.tab = None

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(outer)

        # Sidebar
        side = add_class(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4), "sidebar")
        side.set_size_request(250, -1)
        side.pack_start(label("Settings", "app-title"), False, False, 0)
        self.search = add_class(Gtk.SearchEntry(), "search")
        self.search.set_placeholder_text("Search settings")
        self.search.connect("search-changed", self.on_search)
        self.search.connect("activate", self.on_search_enter)
        side.pack_start(self.search, False, False, 8)
        self.nav = Gtk.ListBox()
        self.nav.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav.connect("row-selected", self.on_nav)
        for cat in self.categories:
            r = add_class(Gtk.ListBoxRow(), "nav")
            r.cat = cat
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.pack_start(label(cat["icon"], "nav-icon", xalign=0.5), False, False, 0)
            box.pack_start(label(cat["name"]), True, True, 0)
            r.add(box)
            self.nav.add(r)
        side.pack_start(self.nav, False, False, 0)
        side.pack_end(label("Ctrl+F search  ·  Esc close\nakim-dotfiles", "foot"), False, False, 0)
        outer.pack_start(side, False, False, 0)

        # Main area
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = add_class(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14), "header")
        self.h_icon = label("", "header-icon", xalign=0.5)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        titles.set_valign(Gtk.Align.CENTER)
        self.h_title = label("", "header-title")
        self.h_sub = label("", "dim", "small")
        titles.pack_start(self.h_title, False, False, 0)
        titles.pack_start(self.h_sub, False, False, 0)
        header.pack_start(self.h_icon, False, False, 0)
        header.pack_start(titles, True, True, 0)
        close = add_class(button("\U000f0156", self.close), "round")
        close.set_valign(Gtk.Align.CENTER)
        header.pack_end(close, False, False, 0)
        main.pack_start(header, False, False, 0)

        self.tabs = add_class(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8), "tabs")
        main.pack_start(self.tabs, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.content = add_class(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), "content")
        scroller.add(self.content)
        main.pack_start(scroller, True, True, 0)

        self.help = label("", "help", wrap=True)
        main.pack_end(self.help, False, False, 0)
        outer.pack_start(main, True, True, 0)

        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)
        self.nav.select_row(self.nav.get_row_at_index(0))

    # -------------------------------------------------------------- chrome
    def reload_colors(self):
        try:
            mtime = (HOME / ".cache" / "wal" / "colors.json").stat().st_mtime
        except OSError:
            mtime = 0
        if mtime != self.colors_mtime:
            self.colors_mtime = mtime
            provider = Gtk.CssProvider()
            provider.load_from_data(css_for(load_colors()).encode())
            screen = Gdk.Screen.get_default()
            if self.css:
                Gtk.StyleContext.remove_provider_for_screen(screen, self.css)
            Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.css = provider
        return True

    def close(self):
        Gtk.main_quit()

    def on_key(self, _w, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        if event.keyval == Gdk.KEY_Escape:
            if self.search.get_text():
                self.search.set_text("")
            else:
                Gtk.main_quit()
            return True
        if ctrl and event.keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search.grab_focus()
            return True
        # Typing anywhere starts a search (like the launcher)
        ch = Gdk.keyval_to_unicode(event.keyval)
        if not ctrl and ch and chr(ch).isalnum() and not self.search.has_focus() \
                and not isinstance(self.get_focus(), (Gtk.Entry, Gtk.SpinButton)):
            self.search.grab_focus()
            self.search.set_text(self.search.get_text() + chr(ch))
            self.search.set_position(-1)
            return True
        return False

    def on_search(self, entry):
        term = entry.get_text().strip().lower()
        first = None
        for r in self.nav.get_children():
            cat = r.cat
            hay = " ".join([cat["name"], cat["sub"], cat["keywords"], *[t[0] for t in cat["tabs"]]]).lower()
            visible = not term or all(w in hay for w in term.split())
            r.set_visible(visible)
            if visible and first is None:
                first = r
        if term and first is not None:
            self.nav.select_row(first)
            # jump to the tab whose name or keywords match
            for tab in first.cat["tabs"]:
                name, kw = tab[0], tab[3] if len(tab) > 3 else ""
                if any(w in (name + " " + kw).lower() for w in term.split()):
                    self.show_tab(name)
                    break

    def on_search_enter(self, _entry):
        self.nav.grab_focus()

    def on_nav(self, _lb, r):
        if r is None:
            return
        self.current = r.cat
        self.h_icon.set_text(r.cat["icon"])
        self.h_title.set_text(r.cat["name"])
        self.h_sub.set_text(r.cat["sub"])
        for child in self.tabs.get_children():
            self.tabs.remove(child)
        tabs = r.cat["tabs"]
        self.tab_buttons = {}
        for t in tabs:
            b = add_class(Gtk.ToggleButton(label=t[0]), "chip")
            b.set_focus_on_click(False)
            b.connect("toggled", self.on_tab_toggled, t[0])
            self.tab_buttons[t[0]] = b
            self.tabs.pack_start(b, False, False, 0)
        self.tabs.set_visible(len(tabs) > 1)
        self.tabs.show_all()
        self.tabs.set_visible(len(tabs) > 1)
        self.show_tab(tabs[0][0])

    def on_tab_toggled(self, btn, name):
        if btn.get_active() and name != self.tab:
            self.show_tab(name)
        elif not btn.get_active() and name == self.tab:
            btn.set_active(True)            # one tab always selected

    def show_tab(self, name):
        self.tab = name
        for n, b in getattr(self, "tab_buttons", {}).items():
            if b.get_active() != (n == name):
                b.set_active(n == name)
        tab = next(t for t in self.current["tabs"] if t[0] == name)
        self.help.set_text("\U000f02fd   " + tab[2])
        self.render(tab[1])

    def render(self, build):
        for child in self.content.get_children():
            self.content.remove(child)
        try:
            for w in build():
                self.content.pack_start(w, False, False, 0)
        except Exception as e:
            self.content.pack_start(group(row("Could not load this page", str(e))), False, False, 0)
        self.content.show_all()

    def refresh(self):
        """Rebuild the current tab (after a change that alters what it shows)."""
        if self.current and self.tab:
            self.show_tab(self.tab)

    # -------------------------------------------------------------- categories
    def define(self):
        return [
            {"id": "appearance", "icon": "\U000f03d8", "name": "Appearance",
             "sub": "Wallpaper, bar, lock screen and menus", "keywords": "theme look style",
             "tabs": [
                 ("Waybar", self.page_waybar, "Theme, position and size of the status bar. The preview shows where it goes; changes apply right away.", "bar position size theme"),
                 ("Wallpaper", self.page_wallpaper, "Outline draws characters first when switching wallpapers (needs character detection); Classic uses awww wipes and waves.", "wallpaper transition outline"),
                 ("Lock screen", self.page_lock, "The design used by Super + L, idle lock and the power menu.", "lock hyprlock"),
                 ("Menus", self.page_menus, "Radial: ring around the center. Cards: a row of glass cards. Both ask again before Shutdown, Reboot and Logout.", "power menu animations"),
             ]},
            {"id": "display", "icon": "\U000f0379", "name": "Display", "sub": "Brightness and night light",
             "keywords": "screen brightness night light warm blue",
             "tabs": [("Display", self.page_display, "Night light warms the screen colors and comes back after a reboot.", "")]},
            {"id": "network", "icon": "\U000f0928", "name": "Network", "sub": "Wi-Fi", "keywords": "wifi wireless internet",
             "tabs": [("Wi-Fi", self.page_wifi, "Click Connect on a network; secured networks ask for their password once.", "")]},
            {"id": "bluetooth", "icon": "\U000f00af", "name": "Bluetooth", "sub": "Devices", "keywords": "headphones pair",
             "tabs": [("Devices", self.page_bluetooth, "Connected devices show their battery when they report it. Scan looks for new devices for 8 seconds.", "")]},
            {"id": "sound", "icon": "\U000f057e", "name": "Sound", "sub": "Output, input and volume", "keywords": "audio volume speakers microphone",
             "tabs": [("Sound", self.page_sound, "Per-app volume is in the quick panel (Super + N).", "")]},
            {"id": "power", "icon": "\U000f0079", "name": "Power", "sub": "Battery, profile and sleep", "keywords": "battery caffeine profile performance",
             "tabs": [("Power", self.page_power, "Power saver makes the battery last longer; Caffeine keeps the screen awake.", "")]},
            {"id": "input", "icon": "\U000f037d", "name": "Mouse & keyboard", "sub": "Pointer speed", "keywords": "mouse touchpad sensitivity speed",
             "tabs": [("Mouse", self.page_mouse, "Applies immediately and is kept in user-settings.hl.", "")]},
            {"id": "apps", "icon": "\U000f003b", "name": "Default apps", "sub": "Browser, terminal, file manager", "keywords": "browser terminal files default",
             "tabs": [("Apps", self.page_apps, "Only installed apps are listed. Terminal: Super + Return, file manager: Super + F.", "")]},
            {"id": "shortcuts", "icon": "\U000f030c", "name": "Shortcuts", "sub": "Keyboard shortcuts", "keywords": "keys keybinds hotkeys",
             "tabs": [("Shortcuts", self.page_shortcuts, "Click Change, then press the new keys. Your changes are kept in user-binds.hl; Reset puts a shortcut back. If keys stop working while recording, Ctrl + Alt + Esc restores them.", "")]},
            {"id": "about", "icon": "\U000f02fd", "name": "About", "sub": "This system", "keywords": "system info version",
             "tabs": [("About", self.page_about, "Versions and uptime; fastfetch shows more.", "")]},
        ]

    # -------------------------------------------------------------- Appearance
    def layout_state(self):
        parts = run(["python3", str(WAYBAR / "layout.py"), "--get"]).split()
        return (parts + ["capsule", "top", "normal"][len(parts):])[:3]

    def page_waybar(self):
        theme, pos, size = self.layout_state()
        preview = self.bar_preview(pos)
        sel = str(WAYBAR / "select.sh")

        def apply(*args):
            spawn([sel, *args])

        def set_pos(v):
            preview.pos = v
            preview.queue_draw()
            apply("--position", v)

        return [
            preview,
            section("Bar"),
            group(
                row("Theme", "", segmented([(t, t.capitalize()) for t in ("default", "line", "zen", "experimental", "capsule")],
                                           theme, lambda v: apply(v))),
                row("Position", "", segmented([(p, p.capitalize()) for p in ("top", "bottom", "left", "right")], pos, set_pos)),
                row("Size", "Thickness of the bar", segmented([(s, s.capitalize()) for s in ("compact", "normal", "large")],
                                                             size, lambda v: apply("--size", v))),
                row("Gap to windows", "Space between the bar and your windows",
                    slider(self.bar_gap(), 0, 40, lambda v: f"{int(v)} px",
                           lambda v: spawn(["python3", str(WAYBAR / "layout.py"), "--gap", str(int(v))]), delay=250)),
            ),
        ]

    @staticmethod
    def bar_gap() -> int:
        try:
            return int(json.loads((HOME / ".config" / "waybar" / "layout.json").read_text(encoding="utf-8", errors="replace")).get("gap", 12))
        except (OSError, ValueError, TypeError):
            return 12

    def bar_preview(self, pos):
        area = add_class(Gtk.DrawingArea(), "preview")
        area.set_size_request(-1, 150)
        area.pos = pos
        wall = os.path.realpath(WALLPAPERS / "current.jpg")
        area.pix = None
        try:
            area.pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(wall, 900, 300, True)
        except Exception:
            pass

        def draw(w, cr):
            W, H = w.get_allocated_width(), w.get_allocated_height()
            cr.save()
            r = 14
            cr.new_sub_path()
            cr.arc(W - r, r, r, -1.5708, 0); cr.arc(W - r, H - r, r, 0, 1.5708)
            cr.arc(r, H - r, r, 1.5708, 3.1416); cr.arc(r, r, r, 3.1416, 4.7124)
            cr.close_path()
            cr.clip()
            if w.pix:
                pw, ph = w.pix.get_width(), w.pix.get_height()
                s = max(W / pw, H / ph)
                cr.scale(s, s)
                Gdk.cairo_set_source_pixbuf(cr, w.pix, (W / s - pw) / 2, (H / s - ph) / 2)
                cr.paint()
                cr.identity_matrix()
            else:
                cr.set_source_rgb(0.2, 0.22, 0.3)
                cr.paint()
            cr.set_source_rgba(0.08, 0.08, 0.12, 0.72)
            t = 18
            boxes = {"top": (W * 0.06, 8, W * 0.88, t), "bottom": (W * 0.06, H - 8 - t, W * 0.88, t),
                     "left": (8, H * 0.1, t, H * 0.8), "right": (W - 8 - t, H * 0.1, t, H * 0.8)}
            x, y, bw, bh = boxes.get(w.pos, boxes["top"])
            rr = 7
            cr.new_sub_path()
            cr.arc(x + bw - rr, y + rr, rr, -1.5708, 0); cr.arc(x + bw - rr, y + bh - rr, rr, 0, 1.5708)
            cr.arc(x + rr, y + bh - rr, rr, 1.5708, 3.1416); cr.arc(x + rr, y + rr, rr, 3.1416, 4.7124)
            cr.close_path()
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.select_font_face("sans")
            cr.set_font_size(12)
            cr.move_to(40 if w.pos == "left" else 14, H - 14 if w.pos != "bottom" else 24)
            cr.show_text("Preview · changes apply immediately")
            cr.restore()

        area.connect("draw", draw)
        return area

    def page_wallpaper(self):
        mode_file = HYPR / "wallpaper-transition"
        mode = mode_file.read_text(encoding="utf-8", errors="replace").strip() if mode_file.exists() else "outline"
        data = HOME / ".local" / "share" / "wallfx"
        installed = (data / "isnet-anime.onnx").is_file()
        setup = str(SCRIPTS / "wallfx" / "wallfx-setup.sh")

        def set_mode(v):
            mode_file.write_text(v + "\n", encoding="utf-8")

        def remove():
            spawn(["bash", setup, "--remove"])
            GLib.timeout_add(800, lambda: (self.refresh(), False)[1])

        if installed:
            status = Gtk.Box(spacing=10)
            status.pack_start(label("\U000f012c  Installed", "ok"), False, False, 0)
            status.pack_start(button("Remove", remove), False, False, 0)
        else:
            status = button("Set up", lambda: spawn(["kitty", "--class", "wallfx-setup", "--hold", "-e", "bash", setup]))
        return [
            section("Wallpaper"),
            group(
                row("Pick a wallpaper", "Opens the carousel (Super + W)", button("Open", lambda: spawn([str(SCRIPTS / "rofi-wallpaper.sh")]))),
                row("Transition", "How the next wallpaper appears",
                    segmented([("outline", "Outline / colonies"), ("classic", "Classic")], mode, set_mode)),
                row("Character detection", "Lets the outline follow characters · about 400 MB", status),
            ),
        ]

    def page_lock(self):
        active = HYPR / "hyprlock" / "active.conf"
        m = re.search(r"hyprlock/([a-z]+)\.conf", active.read_text(encoding="utf-8", errors="replace") if active.exists() else "")
        cur = m.group(1) if m else "classic"
        styles = [("classic", "Classic", "Avatar, name, password"), ("clock", "Clock first", "Big clock, live status"),
                  ("card", "Glass card", "Frosted card on the right"), ("minimal", "Minimal", "Time and password only")]
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, column_homogeneous=True)
        buttons = []
        state = {"busy": False}

        def pick(btn, value):
            if state["busy"]:
                return
            state["busy"] = True
            for b in buttons:
                b.set_active(b is btn)
            state["busy"] = False
            active.write_text(f"source = ~/.config/hypr/hyprlock/{value}.conf\n", encoding="utf-8")
            notify(f"Lock screen: {value}")

        for i, (value, name, desc) in enumerate(styles):
            b = add_class(Gtk.ToggleButton(), "card")
            b.set_focus_on_click(False)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.pack_start(label(name, "card-title", xalign=0.5), False, False, 0)
            box.pack_start(label(desc, "dim", "small", xalign=0.5), False, False, 0)
            b.add(box)
            b.set_active(value == cur)
            b.connect("toggled", pick, value)
            buttons.append(b)
            grid.attach(b, i, 0, 1, 1)
        return [section("Style"), grid,
                group(row("Try it", "Locks the screen now", button("Lock now", lambda: spawn("pidof hyprlock || hyprlock"))))]

    def page_menus(self):
        style_file = HYPR / "power-menu-style"
        style = style_file.read_text(encoding="utf-8", errors="replace").strip() if style_file.exists() else "radial"
        anim = "int: 0" not in run(["hyprctl", "getoption", "animations:enabled"])

        def set_anim(on):
            spawn(["hyprctl", "keyword", "animations:enabled", "1" if on else "0"])
            set_block("animations", f"animations {{\n    enabled = {'true' if on else 'false'}\n}}")

        return [
            section("Power menu (Super + Esc)"),
            group(row("Style", "", segmented([("radial", "Radial"), ("cards", "Cards")], style,
                                             lambda v: style_file.write_text(v + "\n", encoding="utf-8"))),
                  row("Open it", "", button("Power menu", lambda: spawn([str(SCRIPTS / "snmenu-toggle.sh")])))),
            section("Effects"),
            group(row("Animations", "Window and workspace animations; off is snappier and saves battery", switch(anim, set_anim))),
        ]

    # -------------------------------------------------------------- Display
    def page_display(self):
        bri = None
        devs = sorted(Path("/sys/class/backlight").glob("*"))
        if devs:
            try:
                bri = round(int((devs[0] / "brightness").read_text(encoding="utf-8", errors="replace")) * 100 / int((devs[0] / "max_brightness").read_text(encoding="utf-8", errors="replace")))
            except (OSError, ValueError, ZeroDivisionError):
                pass
        night = run([str(SCRIPTS / "nightlight.sh"), "status"])
        night_on = night.isdigit()
        temps = [("4500", "Soft"), ("3500", "Warm"), ("2700", "Very warm")]
        current_temp = night if night_on else (run(f"cat {HYPR}/nightlight.last 2>/dev/null") or "3500")

        def set_night(on):
            spawn([str(SCRIPTS / "nightlight.sh"), self._temp if on else "off"])

        def set_temp(v):
            self._temp = v
            if run([str(SCRIPTS / "nightlight.sh"), "status"]).isdigit():
                spawn([str(SCRIPTS / "nightlight.sh"), v])

        self._temp = current_temp if current_temp in dict(temps) else "3500"
        rows = []
        if bri is not None:
            rows.append(row("Brightness", "", slider(bri, 1, 100, lambda v: f"{int(v)}%",
                                                      lambda v: spawn(["brightnessctl", "-q", "set", f"{int(v)}%"]))))
        rows += [row("Night light", "Warmer colors, easier on the eyes in the evening", switch(night_on, set_night)),
                 row("Warmth", "", segmented(temps, self._temp, set_temp))]
        return [group(*rows)]

    # -------------------------------------------------------------- Network
    def page_wifi(self):
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        holder.pack_start(placeholder("Looking for networks…"), False, False, 0)

        def work():
            radio = run(["nmcli", "-t", "radio", "wifi"]) == "enabled"
            nets, seen = [], set()
            out = run(["nmcli", "-t", "-e", "no", "-f", "IN-USE,SIGNAL,SECURITY,SSID", "dev", "wifi", "list"], timeout=8)
            for line in out.splitlines():
                parts = line.split(":", 3)
                if len(parts) == 4 and parts[3] and parts[3] not in seen:
                    seen.add(parts[3])
                    nets.append({"active": parts[0] == "*", "signal": int(parts[1] or 0),
                                 "secure": parts[2] not in ("", "--"), "ssid": parts[3]})
            known = set(run(["nmcli", "-t", "-f", "NAME", "con", "show"]).splitlines())
            nets.sort(key=lambda n: (not n["active"], -n["signal"]))
            return radio, nets, known

        def fill(result):
            for c in holder.get_children():
                holder.remove(c)
            if result is None:
                holder.pack_start(placeholder("NetworkManager is not available"), False, False, 0)
                holder.show_all()
                return
            radio, nets, known = result

            def set_radio(on):
                spawn(["nmcli", "radio", "wifi", "on" if on else "off"])
                GLib.timeout_add(1500, lambda: (self.refresh(), False)[1])

            holder.pack_start(group(row("Wi-Fi", "", switch(radio, set_radio)),
                                    row("Rescan", "", button("Scan", lambda: (spawn(["nmcli", "dev", "wifi", "rescan"]),
                                                                            GLib.timeout_add(3000, lambda: (self.refresh(), False)[1]))))),
                              False, False, 0)
            if radio:
                holder.pack_start(section("Networks"), False, False, 0)
                rows = []
                for n in nets[:14]:
                    bars = "\U000f0928" if n["signal"] >= 75 else "\U000f0925" if n["signal"] >= 50 else "\U000f0922" if n["signal"] >= 25 else "\U000f091f"
                    sub = ("Connected · " if n["active"] else "") + ("\U000f033e secured" if n["secure"] else "open") + f" · {n['signal']}%"
                    if n["active"]:
                        ctl = button("Disconnect", lambda: (spawn("nmcli dev disconnect $(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2==\"wifi\"{print $1;exit}')"),
                                                            GLib.timeout_add(1500, lambda: (self.refresh(), False)[1])))
                    else:
                        ctl = button("Connect", lambda n=n: self.wifi_connect(n, known))
                    rows.append(row(f"{bars}   {n['ssid']}", sub, ctl))
                holder.pack_start(group(*rows) if rows else placeholder("No networks found"), False, False, 0)
            holder.show_all()

        in_background(work, fill)
        return [holder]

    def wifi_connect(self, net, known):
        ssid = net["ssid"]
        if ssid in known or not net["secure"]:
            cmd = ["nmcli", "con", "up", "id", ssid] if ssid in known else ["nmcli", "dev", "wifi", "connect", ssid]
        else:
            dialog = Gtk.Dialog(title=f"Connect to {ssid}", transient_for=self, modal=True)
            dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Connect", Gtk.ResponseType.OK)
            entry = Gtk.Entry(visibility=False, activates_default=True)
            entry.set_placeholder_text("Password")
            dialog.set_default_response(Gtk.ResponseType.OK)
            box = dialog.get_content_area()
            box.set_spacing(10)
            box.set_border_width(14)
            box.add(label(f"Password for {ssid}"))
            box.add(entry)
            dialog.show_all()
            resp, pw = dialog.run(), entry.get_text()
            dialog.destroy()
            if resp != Gtk.ResponseType.OK or not pw:
                return
            cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", pw]
        notify(f"Connecting to {ssid}…")

        def work():
            ok = subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
            if not ok and len(cmd) > 5:
                run(["nmcli", "con", "delete", "id", ssid])      # don't keep a wrong password
            return ok

        in_background(work, lambda ok: (notify(f"Connected to {ssid}" if ok else f"Could not connect to {ssid}"), self.refresh()))

    # -------------------------------------------------------------- Bluetooth
    def page_bluetooth(self):
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        holder.pack_start(placeholder("Reading devices…"), False, False, 0)

        def work():
            powered = "Powered: yes" in run(["bluetoothctl", "show"])
            devices = []
            if powered:
                for line in run(["bluetoothctl", "devices"]).splitlines():
                    parts = line.split(" ", 2)
                    if len(parts) < 3:
                        continue
                    info = run(["bluetoothctl", "info", parts[1]])
                    bat = re.search(r"Battery Percentage:.*\((\d+)\)", info)
                    devices.append({"mac": parts[1], "name": parts[2],
                                    "connected": "Connected: yes" in info, "paired": "Paired: yes" in info,
                                    "battery": bat.group(1) if bat else ""})
            devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
            return powered, devices

        def fill(result):
            for c in holder.get_children():
                holder.remove(c)
            powered, devices = result or (False, [])

            def set_power(on):
                spawn(["bluetoothctl", "power", "on" if on else "off"])
                GLib.timeout_add(1200, lambda: (self.refresh(), False)[1])

            holder.pack_start(group(row("Bluetooth", "", switch(powered, set_power))), False, False, 0)
            if powered:
                holder.pack_start(section("Devices"), False, False, 0)
                rows = []
                for d in devices[:14]:
                    state = "Connected" if d["connected"] else "Paired" if d["paired"] else "New"
                    sub = state + (f" · \U000f0079 {d['battery']}%" if d["battery"] else "")
                    if d["connected"]:
                        act, text = ["bluetoothctl", "disconnect", d["mac"]], "Disconnect"
                    elif d["paired"]:
                        act, text = ["bluetoothctl", "connect", d["mac"]], "Connect"
                    else:
                        act, text = f"bluetoothctl pair {d['mac']} && bluetoothctl trust {d['mac']} && bluetoothctl connect {d['mac']}", "Pair"
                    rows.append(row(d["name"], sub, button(text, lambda act=act: (spawn(act), GLib.timeout_add(3000, lambda: (self.refresh(), False)[1])))))
                holder.pack_start(group(*rows) if rows else placeholder("No devices yet: press Scan"), False, False, 0)
                holder.pack_start(group(row("Look for new devices", "Scans for 8 seconds",
                                            button("Scan", lambda: (spawn("bluetoothctl --timeout 8 scan on"),
                                                                    notify("Scanning for 8 seconds…"),
                                                                    GLib.timeout_add(9000, lambda: (self.refresh(), False)[1]))))),
                                  False, False, 0)
            holder.show_all()

        in_background(work, fill)
        return [holder]

    # -------------------------------------------------------------- Sound
    def page_sound(self):
        def vol(target):
            out = run(["wpctl", "get-volume", target])
            try:
                return round(float(out.split()[1]) * 100), "MUTED" in out
            except (IndexError, ValueError):
                return None, False

        out_vol, _ = vol("@DEFAULT_AUDIO_SINK@")
        mic_vol, mic_muted = vol("@DEFAULT_AUDIO_SOURCE@")

        def devices(kind):
            try:
                items = json.loads(run(["pactl", "-f", "json", "list", kind]) or "[]")
            except ValueError:
                items = []
            default = run(["pactl", "get-default-sink" if kind == "sinks" else "get-default-source"])
            return [(d["name"], d.get("description") or d["name"]) for d in items
                    if not d["name"].endswith(".monitor")], default

        sinks, def_sink = devices("sinks")
        sources, def_source = devices("sources")
        rows = []
        if out_vol is not None:
            rows.append(row("Volume", "", slider(out_vol, 0, 150, lambda v: f"{int(v)}%",
                                                  lambda v: spawn(["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", f"{int(v)}%"]))))
        if sinks:
            rows.append(row("Output", "", dropdown(sinks, def_sink, lambda n: spawn(["pactl", "set-default-sink", n]))))
        if mic_vol is not None:
            rows.append(row("Microphone level", "", slider(mic_vol, 0, 100, lambda v: f"{int(v)}%",
                                                            lambda v: spawn(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", f"{int(v)}%"]))))
            rows.append(row("Mute microphone", "", switch(mic_muted, lambda on: spawn(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1" if on else "0"]))))
        if sources:
            rows.append(row("Input", "", dropdown(sources, def_source, lambda n: spawn(["pactl", "set-default-source", n]))))
        rows.append(row("Advanced", "Per-app streams and device profiles", button("Open mixer", lambda: spawn(["pavucontrol"]))))
        return [group(*rows)]

    # -------------------------------------------------------------- Power
    def page_power(self):
        rows = []
        for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
            try:
                cap = (bat / "capacity").read_text(encoding="utf-8", errors="replace").strip()
                status = (bat / "status").read_text(encoding="utf-8", errors="replace").strip()
                rows.append(row("Battery", status, label(f"{cap}%", "dim")))
            except OSError:
                pass
            break
        if have("powerprofilesctl"):
            cur = run(["powerprofilesctl", "get"])
            rows.append(row("Power profile", "", segmented([("power-saver", "Saver"), ("balanced", "Balanced"), ("performance", "Performance")],
                                                           cur, lambda v: spawn(["powerprofilesctl", "set", v]))))
        caffeine = (HOME / ".cache" / "caffeine_active").exists()
        rows.append(row("Caffeine", "Keep the screen awake (no lock, no sleep)",
                        switch(caffeine, lambda on: spawn(["bash", str(SCRIPTS / "caffeine-toggle.sh")]))))
        return [group(*rows)]

    # -------------------------------------------------------------- Mouse
    def page_mouse(self):
        cur = None
        try:
            m = re.findall(r"^\s*sensitivity\s*=\s*(-?[0-9.]+)", USER_SETTINGS.read_text(encoding="utf-8", errors="replace"), re.M)
            cur = float(m[-1]) if m else None
        except OSError:
            pass
        if cur is None:
            m = re.search(r"float:\s*(-?[0-9.]+)", run(["hyprctl", "getoption", "input:sensitivity"]))
            cur = float(m.group(1)) if m else 0.0

        def apply(v):
            v = round(v, 2)
            spawn(["hyprctl", "keyword", "input:sensitivity", str(v)])
            set_block("mouse", f"input {{\n    sensitivity = {v}\n}}")

        return [group(row("Pointer speed", "-1 slowest · 0 default · 1 fastest",
                          slider(cur, -1.0, 1.0, lambda v: f"{v:+.2f}", apply, step=0.05, delay=300)))]

    # -------------------------------------------------------------- Default apps
    def page_apps(self):
        # Browsers: every installed app in the WebBrowser category
        dirs = [Path("/usr/share/applications"), HOME / ".local/share/applications",
                Path("/var/lib/flatpak/exports/share/applications"), HOME / ".local/share/flatpak/exports/share/applications"]
        browsers, seen = [], set()
        for d in dirs:
            for f in sorted(d.glob("*.desktop")) if d.is_dir() else []:
                if f.name in seen:
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if re.search(r"^Categories=.*WebBrowser", text, re.M) and not re.search(r"^NoDisplay=true", text, re.M | re.I):
                    seen.add(f.name)
                    name = re.search(r"^Name=(.*)$", text, re.M)
                    browsers.append((f.name, name.group(1) if name else f.name))
        cur_browser = run(["xdg-settings", "get", "default-web-browser"])

        def set_browser(desktop):
            spawn(["xdg-settings", "set", "default-web-browser", desktop])
            spawn(["xdg-mime", "default", desktop, "x-scheme-handler/http", "x-scheme-handler/https", "text/html"])

        terms = [(b, n) for b, n in (("kitty", "Kitty"), ("alacritty", "Alacritty"), ("foot", "Foot"), ("wezterm", "WezTerm"),
                                     ("gnome-terminal", "GNOME Terminal"), ("konsole", "Konsole")) if have(b)]
        fms = [(b, n) for b, n in (("nautilus", "Nautilus"), ("thunar", "Thunar"), ("nemo", "Nemo"), ("dolphin", "Dolphin"),
                                   ("pcmanfm", "PCManFM")) if have(b)]

        def set_fm(binary):
            set_app_var("fileManager", "nautilus --new-window" if binary == "nautilus" else binary)
            desk = run(f"grep -l '^Exec={binary}' /usr/share/applications/*.desktop 2>/dev/null | head -1")
            if desk:
                spawn(["xdg-mime", "default", os.path.basename(desk), "inode/directory"])

        rows = []
        if browsers:
            rows.append(row("Web browser", "Super + B and links", dropdown(browsers, cur_browser, set_browser)))
        if terms:
            rows.append(row("Terminal", "Super + Return", dropdown(terms, read_app_var("terminal", "kitty"),
                                                                   lambda b: set_app_var("terminal", b))))
        if fms:
            rows.append(row("File manager", "Super + F", dropdown(fms, read_app_var("fileManager", "nautilus"), set_fm)))
        return [group(*rows)] if rows else [placeholder("No supported apps found")]

    # -------------------------------------------------------------- Shortcuts
    def page_shortcuts(self):
        try:
            binds = parse_binds((HYPR / "hyprland.hl").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            binds = []
        if not binds:
            return [placeholder("No shortcuts found in hyprland.hl")]
        overrides = read_overrides()
        names = cheatsheet_descriptions()
        widgets = []
        if overrides:
            widgets.append(group(row(f"{len(overrides)} shortcut{'s' if len(overrides) > 1 else ''} changed",
                                     "Your changes are kept in user-binds.hl",
                                     button("Reset all", lambda: (reset_overrides(), self.refresh())))))
        for title in ("Apps and menus", "Windows", "Workspaces"):
            rows = []
            for b in [b for b in binds if bind_group(b) == title]:
                ident = combo_id(b["mods"], b["key"])
                mods, key = overrides.get(ident, (b["mods"], b["key"]))
                controls = Gtk.Box(spacing=8)
                keys = label(combo_label(mods, key), "dim", "small", xalign=1.0)
                controls.pack_start(keys, False, False, 0)
                if ident in overrides:
                    controls.pack_start(button("Reset", lambda b=b: (write_override(b, b["mods"], b["key"]), self.refresh())),
                                        False, False, 0)
                controls.pack_start(button("Change", lambda b=b: self.change_shortcut(b, binds)), False, False, 0)
                sub = "changed" if ident in overrides else ""
                rows.append(row(describe(b, names), sub, controls))
            if rows:
                widgets += [section(title), group(*rows)]
        return widgets

    def change_shortcut(self, bind, binds):
        """Record a new key combination for `bind` and save it as an override."""
        got = self.capture_keys(describe(bind, cheatsheet_descriptions()))
        if not got:
            return
        mods, key = got
        new_id = combo_id(mods, key)
        overrides = read_overrides()
        for other in binds:
            if other is bind:
                continue
            o_mods, o_key = overrides.get(combo_id(other["mods"], other["key"]), (other["mods"], other["key"]))
            if combo_id(o_mods, o_key) == new_id:
                notify(f"{combo_label(mods, key)} is already used by: {describe(other, cheatsheet_descriptions())}")
                return
        write_override(bind, mods, key)
        notify(f"New shortcut: {combo_label(mods, key)}")
        self.refresh()

    def capture_keys(self, what):
        """Modal dialog that returns (mods, key) of the next combination pressed, or None.
        Hyprland is switched to an empty submap meanwhile, so existing shortcuts don't fire."""
        modifier_keys = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L", "Super_R",
                         "Meta_L", "Meta_R", "ISO_Level3_Shift", "Hyper_L", "Hyper_R", "Caps_Lock"}
        dialog = Gtk.Dialog(title="New shortcut", transient_for=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_border_width(18)
        box.add(label(f"Press the new shortcut for:\n{what}", "row-title"))
        hint = label("Esc to cancel", "dim", "small")
        box.add(hint)
        result = {}

        def on_key(_w, event):
            name = Gdk.keyval_name(event.keyval) or ""
            if name in modifier_keys:
                return True
            state = event.state
            mods = []
            if state & Gdk.ModifierType.MOD4_MASK or state & Gdk.ModifierType.SUPER_MASK:
                mods.append("SUPER")
            if state & Gdk.ModifierType.CONTROL_MASK:
                mods.append("CTRL")
            if state & Gdk.ModifierType.MOD1_MASK:
                mods.append("ALT")
            if state & Gdk.ModifierType.SHIFT_MASK:
                mods.append("SHIFT")
            if name == "Escape" and not mods:
                dialog.response(Gtk.ResponseType.CANCEL)
                return True
            # Unshifted key name, the way Hyprland matches it (Shift + & is still "ampersand")
            keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
            ok, keyval, *_ = keymap.translate_keyboard_state(event.hardware_keycode, 0, event.group)
            key = Gdk.keyval_name(keyval) if ok else name
            if not mods and not re.match(r"^(F\d+|Print|XF86\w+)$", key or ""):
                hint.set_text("Use at least one of Super, Ctrl, Alt or Shift (or an F key)")
                return True
            result["combo"] = (norm_mods(" ".join(mods)), key)
            dialog.response(Gtk.ResponseType.OK)
            return True

        dialog.connect("key-press-event", on_key)
        self.capturing = True
        run(["hyprctl", "dispatch", "submap", "settings-capture"])
        try:
            dialog.show_all()
            dialog.run()
        finally:
            run(["hyprctl", "dispatch", "submap", "reset"])
            self.capturing = False
            dialog.destroy()
        return result.get("combo")

    # -------------------------------------------------------------- About
    def page_about(self):
        os_name = "Linux"
        try:
            m = re.search(r'^PRETTY_NAME="?([^"\n]+)', Path("/etc/os-release").read_text(encoding="utf-8", errors="replace"), re.M)
            os_name = m.group(1) if m else os_name
        except OSError:
            pass
        hypr = (run(["hyprctl", "version"]).splitlines() or [""])[0].replace("Hyprland ", "")
        cpu = ""
        try:
            m = re.search(r"^model name\s*:\s*(.+)$", Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace"), re.M)
            cpu = m.group(1) if m else ""
        except OSError:
            pass
        mem = ""
        try:
            kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace")).group(1))
            mem = f"{kb / 1048576:.1f} GiB"
        except (OSError, AttributeError):
            pass
        try:
            secs = int(float(Path("/proc/uptime").read_text(encoding="utf-8", errors="replace").split()[0]))
            up = f"{secs // 3600}h {secs // 60 % 60:02d}m"
        except OSError:
            up = ""
        rows = [row("System", os_name), row("Kernel", run(["uname", "-r"]))]
        if hypr:
            rows.append(row("Hyprland", hypr[:60]))
        if cpu:
            rows.append(row("Processor", cpu))
        if mem:
            rows.append(row("Memory", mem))
        if up:
            rows.append(row("Uptime", up))
        rows.append(row("More details", "", button("fastfetch", lambda: spawn(["kitty", "--hold", "fastfetch"]))))
        return [group(*rows)]


def main():
    # Toggle: a second launch closes the open window
    if PID_FILE.exists():
        try:
            os.kill(int(PID_FILE.read_text(encoding="utf-8", errors="replace").strip()), 15)
            PID_FILE.unlink(missing_ok=True)
            return
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    win = None
    try:
        win = Settings()
        win.show_all()
        Gtk.main()
    finally:
        if win is not None and win.capturing:      # never leave Hyprland in the capture submap
            run(["hyprctl", "dispatch", "submap", "reset"])
        try:
            if PID_FILE.read_text(encoding="utf-8", errors="replace").strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
