#!/usr/bin/env python3
"""record-border.py X Y W H - a red frame around the area being recorded, with a timer.

Drawn on a click-through layer-shell overlay, just OUTSIDE the recorded area so it never shows
in the video. A small "● REC 00:12" pill sits above the area (below it when there's no room).
screenshot.sh starts it with the area from slurp and stops it with the recording.
"""
import math
import sys
import time

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk   # noqa: E402
import cairo                                # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ImportError, ValueError):
    sys.exit(0)

RED = (1.0, 0.2, 0.4)
GAP = 3          # px between the recorded area and the frame
LINE = 3


def main():
    try:
        x, y, w, h = (int(float(v)) for v in sys.argv[1:5])
    except (ValueError, IndexError):
        return 0
    win = Gtk.Window()
    win.set_app_paintable(True)
    if win.get_screen().get_rgba_visual():
        win.set_visual(win.get_screen().get_rgba_visual())
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_namespace(win, "record-border")
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
    GtkLayerShell.set_exclusive_zone(win, -1)
    for e in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
        GtkLayerShell.set_anchor(win, e, True)
    started = time.monotonic()

    def draw(_w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        o = GAP + LINE / 2
        cr.set_source_rgba(*RED, 0.95)
        cr.set_line_width(LINE)
        cr.rectangle(x - o, y - o, w + 2 * o, h + 2 * o)
        cr.stroke()
        secs = int(time.monotonic() - started)
        label = f"REC  {secs // 60:02d}:{secs % 60:02d}"
        cr.select_font_face("JetBrainsMono Nerd Font", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        ext = cr.text_extents(label)
        pw, ph = ext.width + 40, 26
        px = x - o
        py = y - o - ph - 6 if y - o - ph - 6 > 0 else y + h + o + 6
        cr.set_source_rgba(0.06, 0.06, 0.08, 0.85)
        r = ph / 2
        cr.new_sub_path()
        cr.arc(px + r, py + r, r, math.pi / 2, 3 * math.pi / 2)
        cr.arc(px + pw - r, py + r, r, -math.pi / 2, math.pi / 2)
        cr.close_path()
        cr.fill()
        blink = 0.45 + 0.55 * abs(math.sin(time.monotonic() * 2.5))
        cr.set_source_rgba(*RED, blink)
        cr.arc(px + 15, py + ph / 2, 5, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.move_to(px + 27, py + ph / 2 - ext.y_bearing - ext.height / 2)
        cr.show_text(label)
        return False

    win.connect("draw", draw)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    # Click-through: the overlay takes no input at all
    win.input_shape_combine_region(cairo.Region())
    GLib.timeout_add(200, lambda: (win.queue_draw(), True)[1])
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
