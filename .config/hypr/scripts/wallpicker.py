#!/usr/bin/env python3
"""wallpicker.py - wallpaper picker (Super + W), drawn as an overlay above everything.

    wallpicker.py [carousel|filmstrip|fan]   (default: Settings -> Appearance -> Wallpaper)

    carousel    slanted cards, the chosen one large in the middle
    filmstrip   a strip of thumbnails at the bottom; the screen behind shows the chosen wallpaper
                full size, so you see it for real before keeping it
    fan         the wallpapers fanned like a hand of cards; the chosen one lifts out

Keys: Left / Right (or Up / Down, H / L, the scroll wheel) to move, Enter or Space to keep it,
Esc to close. Mouse: click a card to bring it forward, click it again to keep it.
Prints the chosen file on stdout (rofi-wallpaper.sh applies it with the usual transition).

GTK 3 on a layer-shell overlay: no window and no border; Hyprland fades it in and blurs what is
behind (layerrules on the "wallpicker" namespace). Thumbnails are cached in
~/.cache/wallpaper-picker, so it opens at once after the first time.
"""

import hashlib
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk   # noqa: E402
import cairo                                            # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell           # noqa: E402
except (ImportError, ValueError):
    GtkLayerShell = None

HOME = Path.home()
CACHE = HOME / ".cache" / "wallpaper-picker"
STYLE_FILE = HOME / ".config" / "hypr" / "wallpaper-picker-style"
STYLES = ("carousel", "filmstrip", "fan")
THUMB_W, THUMB_H = 640, 360
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def xdg_dir(name: str, fallback: str) -> Path:
    """A user folder in the user's language (xdg-user-dirs): PICTURES is ~/Images in French,
    ~/Bilder in German... Falls back to ~/<fallback> when it isn't set."""
    try:
        for line in (HOME / ".config" / "user-dirs.dirs").read_text(encoding="utf-8").splitlines():
            if line.startswith(f"XDG_{name}_DIR="):
                value = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(HOME))
                if value.rstrip("/") != str(HOME):
                    return Path(value)
    except OSError:
        pass
    return HOME / fallback


WALLS = xdg_dir("PICTURES", "Pictures") / "wallpapers"


def accent():
    try:
        h = json.loads((HOME / ".cache" / "wal" / "colors.json").read_text(encoding="utf-8"))["colors"]["color1"]
    except (OSError, ValueError, KeyError):
        h = "#7aa2f7"
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def fill_pixbuf(pix, w, h):
    pw, ph = pix.get_width(), pix.get_height()
    s = max(w / pw, h / ph)
    sw, sh = max(w, round(pw * s)), max(h, round(ph * s))
    scaled = pix.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
    return scaled.new_subpixbuf((sw - w) // 2, (sh - h) // 2, w, h)


def load_fill(path, w, h):
    try:
        _f, pw, ph = GdkPixbuf.Pixbuf.get_file_info(path)
        s = max(w / pw, h / ph)
        pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, max(w, round(pw * s)), max(h, round(ph * s)), True)
        return fill_pixbuf(pix, w, h)
    except Exception:
        return None


def thumb(path: Path):
    """640x360 thumbnail, cached on disk by path and modification time."""
    try:
        tag = f"{path}:{path.stat().st_mtime}"
    except OSError:
        return None
    cache = CACHE / (hashlib.md5(tag.encode()).hexdigest() + ".png")
    if cache.exists():
        try:
            return GdkPixbuf.Pixbuf.new_from_file(str(cache))
        except Exception:
            pass
    pix = load_fill(str(path), THUMB_W, THUMB_H)
    if pix:
        CACHE.mkdir(parents=True, exist_ok=True)
        try:
            pix.savev(str(cache), "png", [], [])
        except Exception:
            pass
    return pix


def rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Picker(Gtk.Window):
    def __init__(self, style):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.style = style
        self.files = sorted(p for p in WALLS.iterdir() if p.suffix.lower() in EXTS and p.name != "current.jpg") \
            if WALLS.is_dir() else []
        current = os.path.realpath(WALLS / "current.jpg")
        self.sel = next((i for i, p in enumerate(self.files) if str(p) == current), 0)
        self.pos = float(self.sel)                     # animated position (follows sel)
        self.thumbs = {}
        self.big = {}                                  # filmstrip: full-size backgrounds
        self.big_alpha = 1.0
        self.shown_big = self.sel
        self.prev_big = None
        self.accent = accent()
        self.hits = []                                 # (index, path ops) for clicks
        self.started = time.monotonic()
        self.tick_id = None

        self.set_title("wallpicker")
        self.set_app_paintable(True)
        screen = self.get_screen()
        if screen.get_rgba_visual():
            self.set_visual(screen.get_rgba_visual())
        if GtkLayerShell:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "wallpicker")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_exclusive_zone(self, -1)
            for e in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self, e, True)
        else:
            self.fullscreen()
        self.area = Gtk.DrawingArea()
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.area.connect("draw", self.on_draw)
        self.area.connect("button-press-event", self.on_click)
        self.area.connect("scroll-event", self.on_scroll)
        self.add(self.area)
        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)
        self.scroll_acc = 0.0

        # Thumbnails: the ones around the current wallpaper first
        order = sorted(range(len(self.files)), key=lambda i: abs(i - self.sel))
        for i in order[:9]:
            p = self.files[i]
            cache_hit = (CACHE / (hashlib.md5(f"{p}:{p.stat().st_mtime}".encode()).hexdigest() + ".png")).exists()
            if cache_hit:
                self.thumbs[i] = thumb(p)
        threading.Thread(target=self.load_thumbs, args=(order,), daemon=True).start()
        self.animate()

    # -------------------------------------------------------------- loading
    def load_thumbs(self, order):
        for i in order:
            if i not in self.thumbs:
                pix = thumb(self.files[i])
                GLib.idle_add(self.set_thumb, i, pix)

    def set_thumb(self, i, pix):
        self.thumbs[i] = pix
        self.area.queue_draw()
        return False

    def want_big(self, i):
        """Filmstrip: the chosen wallpaper at screen size, loaded in the background."""
        if i in self.big or self.style != "filmstrip":
            return
        self.big[i] = None
        W, H = self.screen_size()

        def work():
            pix = load_fill(str(self.files[i]), W, H)
            GLib.idle_add(self.set_big, i, pix)
        threading.Thread(target=work, daemon=True).start()

    def screen_size(self):
        """Screen size in device pixels. Not the window's allocation: before the first layout it
        is 1x1, and a wallpaper loaded at that size would be stretched over the whole screen."""
        try:
            display = Gdk.Display.get_default()
            mon = display.get_monitor_at_window(self.get_window()) if self.get_window() else display.get_monitor(0)
            g, sf = mon.get_geometry(), mon.get_scale_factor()
            if g.width > 100:
                return g.width * sf, g.height * sf
        except Exception:
            pass
        W, H = self.get_allocated_width(), self.get_allocated_height()
        return (W, H) if W > 100 else (1920, 1080)

    def set_big(self, i, pix):
        self.big[i] = pix
        if len(self.big) > 6:                          # keep memory small
            for k in [k for k in self.big if abs(k - self.sel) > 3]:
                self.big.pop(k, None)
        self.area.queue_draw()
        return False

    # -------------------------------------------------------------- animation
    def animate(self):
        if self.tick_id is None:
            self.tick_id = self.area.add_tick_callback(self.on_tick)

    def on_tick(self, *_):
        d = self.sel - self.pos
        self.pos += d * 0.22
        moving = abs(d) > 0.002
        if not moving:
            self.pos = float(self.sel)
        if self.style == "filmstrip":
            if self.shown_big != self.sel:
                self.prev_big, self.shown_big, self.big_alpha = self.shown_big, self.sel, 0.0
            if self.big_alpha < 1:
                self.big_alpha = min(1.0, self.big_alpha + 0.12)
                moving = True
        if time.monotonic() - self.started < 0.3:
            moving = True
        self.area.queue_draw()
        if not moving:
            self.tick_id = None
            return False
        return True

    def select(self, i):
        if not self.files:
            return
        self.sel = max(0, min(len(self.files) - 1, i))
        self.want_big(self.sel)
        self.animate()

    # -------------------------------------------------------------- input
    def on_key(self, _w, e):
        k = e.keyval
        if k == Gdk.KEY_Escape:
            Gtk.main_quit()
        elif k in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_l, Gdk.KEY_j, Gdk.KEY_Tab):
            self.select(self.sel + 1)
        elif k in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_h, Gdk.KEY_k, Gdk.KEY_ISO_Left_Tab):
            self.select(self.sel - 1)
        elif k == Gdk.KEY_Home:
            self.select(0)
        elif k == Gdk.KEY_End:
            self.select(len(self.files) - 1)
        elif k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self.choose()
        else:
            return False
        return True

    def on_scroll(self, _w, e):
        ok, _dx, dy = e.get_scroll_deltas()
        if not ok:
            ok, direction = e.get_scroll_direction()
            dy = {Gdk.ScrollDirection.UP: -1, Gdk.ScrollDirection.DOWN: 1,
                  Gdk.ScrollDirection.LEFT: -1, Gdk.ScrollDirection.RIGHT: 1}.get(direction, 0) if ok else 0
        self.scroll_acc += dy
        if abs(self.scroll_acc) >= 1:
            self.select(self.sel + (1 if self.scroll_acc > 0 else -1))
            self.scroll_acc = 0.0
        return True

    def on_click(self, _w, e):
        if e.button != 1:
            Gtk.main_quit()
            return True
        surf = cairo.ImageSurface(cairo.FORMAT_A8, 1, 1)
        cr = cairo.Context(surf)
        for i, matrix, rect in reversed(self.hits):    # topmost first
            cr.identity_matrix()
            cr.transform(matrix)
            cr.new_path()
            cr.rectangle(*rect)
            cr.identity_matrix()
            if cr.in_fill(e.x, e.y):
                if i == self.sel:
                    self.choose()
                else:
                    self.select(i)
                return True
        Gtk.main_quit()                                # click outside the cards
        return True

    def choose(self):
        if self.files:
            print(self.files[self.sel], flush=True)
        Gtk.main_quit()

    # -------------------------------------------------------------- drawing
    def card(self, cr, i, x, y, w, h, alpha=1.0, outline=False, radius=14):
        """Thumbnail i in the box (x, y, w, h) of the current transform."""
        self.hits.append((i, cr.get_matrix(), (x, y, w, h)))
        cr.save()
        rounded(cr, x, y, w, h, radius)
        cr.clip()
        pix = self.thumbs.get(i)
        if pix:
            cr.translate(x, y)
            cr.scale(w / pix.get_width(), h / pix.get_height())
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint_with_alpha(alpha)
        else:
            cr.set_source_rgba(1, 1, 1, 0.08 * alpha)
            cr.paint()
        cr.restore()
        if outline:
            cr.set_source_rgba(*self.accent, 1)
            cr.set_line_width(4)
            rounded(cr, x - 2, y - 2, w + 4, h + 4, radius + 2)
            cr.stroke()

    def text(self, cr, s, x, y, size=16, alpha=1.0, center=True, bold=True, pill=False):
        cr.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        ext = cr.text_extents(s)
        tx = x - ext.width / 2 - ext.x_bearing if center else x
        if pill:                                       # readable over any wallpaper
            cr.set_source_rgba(0.05, 0.06, 0.09, 0.72)
            rounded(cr, tx - 14, y - size - 4, ext.width + 28, size + 14, (size + 14) / 2)
            cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.55 * alpha)
        cr.move_to(tx + 1, y + 1)
        cr.show_text(s)
        cr.set_source_rgba(1, 1, 1, alpha)
        cr.move_to(tx, y)
        cr.show_text(s)

    def name(self, i):
        return self.files[i].stem.replace("-", " ").replace("_", " ").title() if self.files else ""

    def on_draw(self, _w, cr):
        W, H = self.get_allocated_width(), self.get_allocated_height()
        fade = min(1.0, (time.monotonic() - self.started) / 0.18)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        self.hits = []
        if not self.files:
            cr.set_source_rgba(0, 0, 0, 0.5 * fade)
            cr.paint()
            self.text(cr, f"No wallpapers in {WALLS}", W / 2, H / 2, 18)
            return False
        cr.push_group()
        {"carousel": self.draw_carousel, "filmstrip": self.draw_filmstrip, "fan": self.draw_fan}[self.style](cr, W, H)
        cr.pop_group_to_source()
        cr.paint_with_alpha(fade)
        return False

    def visible(self, span):
        lo = max(0, int(math.floor(self.pos - span)))
        hi = min(len(self.files) - 1, int(math.ceil(self.pos + span)))
        return range(lo, hi + 1)

    def draw_carousel(self, cr, W, H):
        cr.set_source_rgba(0, 0, 0, 0.42)
        cr.paint()
        cw = W * 0.38
        ch = cw * 9 / 16
        cx, cy = W / 2, H * 0.48
        items = sorted(self.visible(3.4), key=lambda i: -abs(i - self.pos))   # far ones first
        for i in items:
            d = i - self.pos
            ad = min(abs(d), 3.4)
            s = 1 - ad * 0.17
            alpha = max(0.0, 1 - ad * 0.24)
            cr.save()
            cr.translate(cx + d * W * 0.2, cy)
            cr.transform(cairo.Matrix(1, 0, -0.14, 1, 0, 0))                      # slant
            cr.scale(s, s)
            self.card(cr, i, -cw / 2, -ch / 2, cw, ch, alpha, outline=abs(d) < 0.5, radius=18)
            cr.restore()
        self.text(cr, self.name(self.sel), W / 2, cy + ch / 2 + 54, 22)
        self.text(cr, f"{self.sel + 1} / {len(self.files)}   ·   ← →  move   ·   Enter keep   ·   Esc close",
                  W / 2, H - 46, 13, 0.75, bold=False)

    def draw_filmstrip(self, cr, W, H):
        # The chosen wallpaper fills the screen (crossfade from the previous one)
        def paint_full(i, alpha):
            pix = self.big.get(i) or self.thumbs.get(i)
            if not pix or alpha <= 0:
                return
            cr.save()
            cr.scale(W / pix.get_width(), H / pix.get_height())
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint_with_alpha(alpha)
            cr.restore()
        self.want_big(self.sel)
        if self.prev_big is not None and self.big_alpha < 1:
            paint_full(self.prev_big, 1.0)
        paint_full(self.shown_big, self.big_alpha)
        # Strip at the bottom
        tw, th = W * 0.085, W * 0.085 * 9 / 16
        bw, bh = tw * 1.45, th * 1.45
        gap = 14
        strip_h = bh + 64
        panel_w = min(W * 0.86, (tw + gap) * min(len(self.files), 9) + bw)
        px, py = (W - panel_w) / 2, H - strip_h - 34
        cr.set_source_rgba(0.05, 0.06, 0.09, 0.72)
        rounded(cr, px, py, panel_w, strip_h, 22)
        cr.fill()
        cr.save()
        rounded(cr, px, py, panel_w, strip_h, 22)
        cr.clip()
        base_y = py + strip_h - 30
        for i in self.visible(6):
            d = i - self.pos
            k = max(0.0, 1 - abs(d))                                   # 1 for the chosen one
            w, h = tw + (bw - tw) * k, th + (bh - th) * k
            x = W / 2 + d * (tw + gap) + (bw - tw) / 2 * (1 if d > 0 else -1) * min(1, abs(d)) - w / 2
            self.card(cr, i, x, base_y - h, w, h, 0.65 + 0.35 * k, outline=abs(d) < 0.5, radius=10)
        cr.restore()
        self.text(cr, self.name(self.sel), W / 2, py + strip_h - 10, 14)
        self.text(cr, "← →  try   ·   Enter keep   ·   Esc back", W / 2, py - 16, 13, 0.9, bold=False, pill=True)

    def draw_fan(self, cr, W, H):
        cr.set_source_rgba(0, 0, 0, 0.38)
        cr.paint()
        cw = W * 0.24
        ch = cw * 9 / 16
        pivot_x, pivot_y = W / 2, H * 1.35
        radius = pivot_y - H * 0.5
        step = 0.13                                                    # radians between cards
        items = sorted(self.visible(5.5), key=lambda i: -abs(i - self.pos))
        for i in items:
            d = i - self.pos
            lift = max(0.0, 1 - abs(d)) * ch * 0.5
            cr.save()
            cr.translate(pivot_x, pivot_y)
            cr.rotate(d * step)
            cr.translate(0, -radius - lift)
            s = 1 + max(0.0, 1 - abs(d)) * 0.18
            cr.scale(s, s)
            self.card(cr, i, -cw / 2, -ch / 2, cw, ch, 1.0, outline=abs(d) < 0.5, radius=14)
            cr.restore()
        self.text(cr, self.name(self.sel), W / 2, H * 0.5 - ch * 1.25, 22)
        self.text(cr, f"{self.sel + 1} / {len(self.files)}   ·   ← →  move   ·   Enter keep   ·   Esc close",
                  W / 2, H - 40, 13, 0.75, bold=False)


def main():
    style = sys.argv[1] if len(sys.argv) > 1 else ""
    if style not in STYLES:
        try:
            style = STYLE_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            style = ""
    if style not in STYLES:
        style = "carousel"
    win = Picker(style)
    win.show_all()
    win.want_big(win.sel)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
