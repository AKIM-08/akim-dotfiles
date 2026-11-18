#!/usr/bin/env python3
"""
snmenu.py - Power menu (Super + Escape) in two styles, GTK3/Cairo on a layer-shell overlay.

    snmenu.py [--style radial|cards]

radial  a donut with six sections; the selected one pops out in the wallpaper accent and the
        center shows what it will do, plus uptime and battery.
cards   a row of glass cards; the selected card grows and lifts.

Both styles:
  - mouse hover / click, arrow keys or the scroll wheel to pick, Enter or Space to run
  - letter shortcuts: L lock, S suspend, O logout, P power off, H hibernate, R reboot
  - Shutdown, Reboot and Logout need a second click / Enter within 3 s (no accidents)
  - Esc, Q, right-click or a click outside closes it

Actions and icons come from ~/.config/snmenu/layout (the pywal-themed cpmenu layout).
Running it again while it is open closes it.
"""

import json
import math
import os
import subprocess
import sys
import time

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo
except (ImportError, ValueError) as e:
    sys.stderr.write(f"Error loading GTK3/Cairo: {e}\n")
    sys.exit(1)

HAS_LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    HAS_LAYER_SHELL = True
except (ImportError, ValueError):
    pass

FONT = "JetBrainsMono Nerd Font"
CONFIRM_SECONDS = 3.0
DANGEROUS = {"shutdown", "reboot", "logout"}
KEYS = {"lock": "L", "suspend": "S", "logout": "O", "shutdown": "P", "hibernate": "H", "reboot": "R"}
CARD_ORDER = ["lock", "logout", "suspend", "shutdown", "hibernate", "reboot"]
WARN = (0.82, 0.38, 0.37)


# ------------------------------------------------------------------------------ data
def hex_to_rgb(hex_str, default=(0.1, 0.1, 0.1)):
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 6:
        try:
            return tuple(int(hex_str[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        except ValueError:
            pass
    return default


def load_theme():
    theme = {"bg": (0.10, 0.08, 0.14), "fg": (1.0, 1.0, 1.0), "accent": (0.71, 0.24, 0.48)}
    try:
        with open(os.path.expanduser("~/.cache/wal/colors.json"), encoding="utf-8") as f:
            data = json.load(f)
        colors = data.get("colors", {})
        theme["bg"] = hex_to_rgb(data.get("special", {}).get("background", "#14121a"))
        theme["fg"] = hex_to_rgb(data.get("special", {}).get("foreground", "#ffffff"))
        theme["accent"] = hex_to_rgb(colors.get("color1") or colors.get("color9") or "#b53c7a")
    except Exception:
        pass
    bg = theme["bg"]
    theme["overlay"] = (bg[0] * 0.2, bg[1] * 0.2, bg[2] * 0.2, 0.62)
    theme["ring"] = (min(bg[0] * 1.1, 1), min(bg[1] * 1.1, 1), min(bg[2] * 1.1, 1), 0.94)
    theme["hub"] = (bg[0] * 0.55, bg[1] * 0.55, bg[2] * 0.55, 0.88)
    return theme


def load_layout():
    for path in ("~/.config/snmenu/layout", "~/.config/cpmenu/layout"):
        path = os.path.expanduser(path)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                sys.stderr.write(f"Failed to parse {path}: {e}\n")
    return [
        {"label": "suspend", "action": "loginctl lock-session; systemctl suspend", "text": "Suspend", "icon_char": ""},
        {"label": "logout", "action": "hyprctl dispatch exit", "text": "Logout", "icon_char": ""},
        {"label": "shutdown", "action": "systemctl poweroff", "text": "Shutdown", "icon_char": ""},
        {"label": "hibernate", "action": "loginctl lock-session; systemctl hibernate", "text": "Hibernate", "icon_char": ""},
        {"label": "reboot", "action": "systemctl reboot", "text": "Reboot", "icon_char": ""},
        {"label": "lock", "action": "hyprlock", "text": "Lock", "icon_char": ""},
    ]


def system_info() -> str:
    parts = []
    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        h, m = divmod(secs // 60, 60)
        parts.append(f"up {h}h {m:02d}m" if h else f"up {m}m")
    except Exception:
        pass
    try:
        for name in sorted(os.listdir("/sys/class/power_supply")):
            if name.startswith("BAT"):
                with open(f"/sys/class/power_supply/{name}/capacity") as f:
                    parts.append(f"{f.read().strip()}%")
                break
    except Exception:
        pass
    return "  ·  ".join(parts)


# ------------------------------------------------------------------------------ window
class PowerMenu(Gtk.Window):
    def __init__(self, style: str):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.style = style
        self.set_title("snmenu")
        self.set_wmclass("snmenu", "snmenu")

        self.theme = load_theme()
        items = load_layout()
        if style == "cards":
            rank = {name: i for i, name in enumerate(CARD_ORDER)}
            items = sorted(items, key=lambda it: rank.get(it.get("label", ""), len(rank)))
        self.items = items
        self.n = len(items)
        self.info = system_info()

        self.selected = -1
        self.armed = -1
        self.armed_at = 0.0
        self.tick = None
        self.hit = []                     # cards: (x, y, w, h, index)

        # Radial geometry
        self.outer_r, self.inner_r, self.pop = 330.0, 112.0, 22.0

        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        if HAS_LAYER_SHELL:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_exclusive_zone(self, -1)
            for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                         GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, edge, True)
            GtkLayerShell.set_namespace(self, "snmenu")
        else:
            self.fullscreen()
            self.set_decorated(False)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.SCROLL_MASK
                        | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect("draw", self.on_draw)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("button-press-event", self.on_click)
        self.connect("key-press-event", self.on_key)
        self.connect("scroll-event", self.on_scroll)
        self.connect("destroy", Gtk.main_quit)

    # -------------------------------------------------------------- selection & actions
    def label(self, i) -> str:
        return self.items[i].get("label", "")

    def name(self, i) -> str:
        return self.items[i].get("text", self.label(i)).capitalize()

    def select(self, i):
        if i != self.selected:
            self.selected = i
            if self.armed != i:
                self.disarm()
            self.queue_draw()

    def disarm(self):
        self.armed = -1
        if self.tick:
            GLib.source_remove(self.tick)
            self.tick = None

    def on_tick(self):
        if self.armed >= 0 and time.monotonic() - self.armed_at >= CONFIRM_SECONDS:
            self.tick = None
            self.armed = -1
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def activate(self, i):
        if not 0 <= i < self.n:
            return
        if self.label(i) in DANGEROUS and self.armed != i:
            self.selected = i
            self.disarm()
            self.armed, self.armed_at = i, time.monotonic()
            self.tick = GLib.timeout_add(33, self.on_tick)        # animate the countdown
            self.queue_draw()
            return
        action = self.items[i].get("action", "")
        if action:
            try:
                subprocess.Popen(action, shell=True)
            except Exception as e:
                sys.stderr.write(f"Failed to execute '{action}': {e}\n")
        Gtk.main_quit()

    def step(self, delta):
        if self.n:
            self.select(0 if self.selected < 0 else (self.selected + delta) % self.n)

    # -------------------------------------------------------------- input
    def index_at(self, x, y) -> int:
        if self.style == "cards":
            for cx, cy, w, h, i in self.hit:
                if cx <= x <= cx + w and cy <= y <= cy + h:
                    return i
            return -1
        alloc = self.get_allocation()
        dx, dy = x - alloc.width / 2.0, y - alloc.height / 2.0
        dist = math.hypot(dx, dy)
        if dist < self.inner_r or dist > self.outer_r + self.pop + 20:
            return -1
        slice_a = 2 * math.pi / self.n
        angle = math.atan2(dy, dx) % (2 * math.pi)
        return int(((angle + slice_a / 2) % (2 * math.pi)) / slice_a) % self.n

    def on_motion(self, _w, event):
        i = self.index_at(event.x, event.y)
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(win.get_display(), "pointer" if i >= 0 else "default"))
        if i >= 0:
            self.select(i)
        return True

    def on_click(self, _w, event):
        if event.button == 1:
            i = self.index_at(event.x, event.y)
            if i >= 0:
                self.activate(i)
            else:
                Gtk.main_quit()
            return True
        if event.button == 3:
            Gtk.main_quit()
            return True
        return False

    def on_scroll(self, _w, event):
        d = 0
        if event.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT):
            d = 1
        elif event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT):
            d = -1
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            _, dx, dy = event.get_scroll_deltas()
            v = dy or dx
            d = 1 if v > 0.3 else -1 if v < -0.3 else 0
        if d:
            self.step(d)
        return True

    def on_key(self, _w, event):
        k = event.keyval
        if k in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            if self.armed >= 0:
                self.disarm()
                self.queue_draw()
            else:
                Gtk.main_quit()
            return True
        if k in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_Tab):
            self.step(1)
            return True
        if k in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_ISO_Left_Tab):
            self.step(-1)
            return True
        if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            if self.selected >= 0:
                self.activate(self.selected)
            return True
        ch = chr(Gdk.keyval_to_unicode(k) or 0).upper()
        for i in range(self.n):
            if KEYS.get(self.label(i)) == ch:
                self.activate(i)
                return True
        return False

    # -------------------------------------------------------------- drawing helpers
    def text(self, cr, s, size, x, y, bold=False, rgba=(1, 1, 1, 1), center=True):
        layout = self.create_pango_layout(s)
        layout.set_font_description(Pango.FontDescription(f"{FONT}{' Bold' if bold else ''} {size}"))
        _, rect = layout.get_pixel_extents()
        cr.set_source_rgba(*rgba)
        cr.move_to(x - rect.width / 2 - rect.x if center else x, y - rect.height / 2 - rect.y)
        PangoCairo.show_layout(cr, layout)

    def countdown_left(self) -> float:
        return max(0.0, 1.0 - (time.monotonic() - self.armed_at) / CONFIRM_SECONDS)

    def on_draw(self, _w, cr):
        alloc = self.get_allocation()
        cr.set_source_rgba(*self.theme["overlay"])
        cr.paint()
        if self.style == "cards":
            self.draw_cards(cr, alloc.width, alloc.height)
        else:
            self.draw_radial(cr, alloc.width, alloc.height)
        return True

    # -------------------------------------------------------------- radial
    def draw_radial(self, cr, w, h):
        cx, cy = w / 2, h / 2
        fg, acc, t = self.theme["fg"], self.theme["accent"], self.theme
        slice_a = 2 * math.pi / self.n
        gap = 0.012

        cr.new_path()
        cr.arc(cx, cy, self.outer_r, 0, 2 * math.pi)
        cr.arc_negative(cx, cy, self.inner_r, 2 * math.pi, 0)
        cr.set_source_rgba(*t["ring"])
        cr.fill()

        for i in range(self.n):
            mid = i * slice_a
            sel = i == self.selected
            a0, a1 = mid - slice_a / 2 + gap, mid + slice_a / 2 - gap
            ox, oy = (math.cos(mid) * self.pop, math.sin(mid) * self.pop) if sel else (0, 0)
            if sel:
                # soft shadow, then the popped-out section
                for k, alpha in ((10, 0.10), (5, 0.12)):
                    cr.new_path()
                    cr.arc(cx + ox, cy + oy + k, self.outer_r + 4, a0, a1)
                    cr.arc_negative(cx + ox, cy + oy + k, self.inner_r, a1, a0)
                    cr.close_path()
                    cr.set_source_rgba(0, 0, 0, alpha)
                    cr.fill()
                col = WARN if i == self.armed else acc
                cr.new_path()
                cr.arc(cx + ox, cy + oy, self.outer_r, a0, a1)
                cr.arc_negative(cx + ox, cy + oy, self.inner_r, a1, a0)
                cr.close_path()
                cr.set_source_rgba(*col, 0.96)
                cr.fill()
            else:
                cr.new_path()
                cr.arc(cx, cy, self.outer_r - 1, a0, a1)
                cr.arc_negative(cx, cy, self.inner_r + 1, a1, a0)
                cr.close_path()
                cr.set_source_rgba(*fg, 0.035)
                cr.fill()

            r_mid = (self.inner_r + self.outer_r) / 2
            tx, ty = cx + ox + r_mid * math.cos(mid), cy + oy + r_mid * math.sin(mid)
            self.text(cr, self.items[i].get("icon_char", ""), 42 if sel else 36, tx, ty - 14, rgba=(1, 1, 1, 1))
            self.text(cr, self.name(i), 12.5, tx, ty + 32, bold=True, rgba=(1, 1, 1, 1))
            key = KEYS.get(self.label(i))
            if key:
                self.text(cr, key, 9.5, tx, ty + 52, rgba=(1, 1, 1, 0.45))

        # Center hub
        hub_r = self.inner_r - 10
        cr.new_path()
        cr.arc(cx, cy, hub_r, 0, 2 * math.pi)
        cr.set_source_rgba(*t["hub"])
        cr.fill_preserve()
        cr.set_source_rgba(*fg, 0.08)
        cr.set_line_width(1)
        cr.stroke()
        if self.armed >= 0:
            cr.set_line_width(4)
            cr.set_source_rgba(*WARN, 1)
            cr.new_path()
            cr.arc(cx, cy, hub_r - 7, -math.pi / 2, -math.pi / 2 + 2 * math.pi * self.countdown_left())
            cr.stroke()
            self.text(cr, f"{self.name(self.armed)}?", 15, cx, cy - 8, bold=True)
            self.text(cr, "click / Enter again", 9, cx, cy + 14, rgba=(1, 1, 1, 0.6))
        elif self.selected >= 0:
            self.text(cr, self.name(self.selected), 15, cx, cy - 14, bold=True)
            if self.info:
                self.text(cr, self.info, 9, cx, cy + 8, rgba=(1, 1, 1, 0.6))
            self.text(cr, "Enter · Esc", 9, cx, cy + 26, rgba=(1, 1, 1, 0.45))
        else:
            self.text(cr, time.strftime("%H:%M"), 20, cx, cy - 10, bold=True)
            if self.info:
                self.text(cr, self.info, 9, cx, cy + 16, rgba=(1, 1, 1, 0.6))

    # -------------------------------------------------------------- cards
    def draw_cards(self, cr, w, h):
        fg, acc = self.theme["fg"], self.theme["accent"]
        cw, ch = 210.0, 330.0
        total = cw * self.n
        x0, y0 = (w - total) / 2, (h - ch) / 2
        radius = 34.0
        self.hit = []

        def rounded(x, y, rw, rh, r_left, r_right):
            cr.new_path()
            cr.arc(x + rw - r_right, y + r_right, r_right, -math.pi / 2, 0) if r_right else cr.move_to(x + rw, y)
            cr.arc(x + rw - r_right, y + rh - r_right, r_right, 0, math.pi / 2) if r_right else cr.line_to(x + rw, y + rh)
            cr.arc(x + r_left, y + rh - r_left, r_left, math.pi / 2, math.pi) if r_left else cr.line_to(x, y + rh)
            cr.arc(x + r_left, y + r_left, r_left, math.pi, 3 * math.pi / 2) if r_left else cr.line_to(x, y)
            cr.close_path()

        order = list(range(self.n))
        if self.selected >= 0:                       # draw the selected card last (on top)
            order.remove(self.selected)
            order.append(self.selected)
        for i in order:
            sel = i == self.selected
            x = x0 + i * cw
            if sel:
                s = 1.12
                sw, sh = cw * s, ch * s
                sx, sy = x - (sw - cw) / 2, y0 - (sh - ch) / 2
                rounded(sx + 2, sy + 14, sw, sh, radius, radius)     # shadow
                cr.set_source_rgba(0, 0, 0, 0.25)
                cr.fill()
                rounded(sx, sy, sw, sh, radius, radius)
                cr.set_source_rgba(*self.theme["ring"][:3], 0.97)
                cr.fill_preserve()
                if i == self.armed:
                    cr.set_source_rgba(*WARN, 0.55)
                else:
                    cr.set_source_rgba(*acc, 0.42)
                cr.fill_preserve()
                cr.set_source_rgba(*fg, 0.18)
                cr.set_line_width(1)
                cr.stroke()
                bx, by, bw, bh = sx, sy, sw, sh
            else:
                left = radius if i == 0 else 0
                right = radius if i == self.n - 1 else 0
                rounded(x, y0, cw, ch, left, right)
                cr.set_source_rgba(*fg, 0.10)
                cr.fill_preserve()
                cr.set_source_rgba(*fg, 0.07)
                cr.set_line_width(1)
                cr.stroke()
                bx, by, bw, bh = x, y0, cw, ch
            self.hit.append((x, y0, cw, ch, i))

            mx = bx + bw / 2
            self.text(cr, self.items[i].get("icon_char", ""), 46 if sel else 40, mx, by + bh * 0.42)
            self.text(cr, self.name(i), 13 if sel else 12, mx, by + bh * 0.80, bold=sel,
                      rgba=(1, 1, 1, 1 if sel else 0.85))
            key = KEYS.get(self.label(i))
            if key:
                self.text(cr, key, 9.5, bx + bw - 22, by + 22, rgba=(1, 1, 1, 0.45))
            if i == self.armed:
                self.text(cr, "press again", 9.5, mx, by + bh * 0.88, rgba=(1, 1, 1, 0.85))
                cr.set_source_rgba(1, 1, 1, 0.85)
                cr.set_line_width(3)
                cr.new_path()
                cr.move_to(bx + 24, by + bh - 16)
                cr.line_to(bx + 24 + (bw - 48) * self.countdown_left(), by + bh - 16)
                cr.stroke()


def main():
    style = "radial"
    if "--style" in sys.argv[1:]:
        idx = sys.argv.index("--style")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] in ("radial", "cards"):
            style = sys.argv[idx + 1]

    pid_file = "/tmp/snmenu.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                os.kill(int(f.read().strip()), 15)
            os.remove(pid_file)
            sys.exit(0)
        except (OSError, ValueError):
            pass
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    try:
        PowerMenu(style).show_all()
        Gtk.main()
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass


if __name__ == "__main__":
    main()
