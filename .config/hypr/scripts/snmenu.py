#!/usr/bin/env python3
"""
snmenu.py - Python GTK3/Cairo circular (radial) CS:GO-style power menu
Drop-in replacement for SNMenu when compiling from source is unavailable.
Reads configuration from ~/.config/snmenu/layout (or ~/.config/cpmenu/layout)
and dynamic wallpaper colors from ~/.cache/wal/colors.json.
"""

import sys
import os
import json
import math
import subprocess

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo
    import cairo
except ImportError as e:
    sys.stderr.write(f"Error loading GTK3/Cairo: {e}\n")
    sys.exit(1)

# Optional GtkLayerShell support for native Wayland overlays
HAS_LAYER_SHELL = False
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
    HAS_LAYER_SHELL = True
except Exception:
    HAS_LAYER_SHELL = False


def hex_to_rgb(hex_str, default=(0.5, 0.5, 0.5)):
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        try:
            return (
                int(hex_str[0:2], 16) / 255.0,
                int(hex_str[2:4], 16) / 255.0,
                int(hex_str[4:6], 16) / 255.0,
            )
        except ValueError:
            pass
    return default


def load_theme():
    colors_file = os.path.expanduser("~/.cache/wal/colors.json")
    theme = {
        "bg": (0.10, 0.08, 0.12),
        "fg": (0.95, 0.95, 0.95),
        "accent": (0.78, 0.28, 0.56),      # Vibrant pink/magenta
        "hover_fg": (0.05, 0.05, 0.05),
        "divider": (0.25, 0.20, 0.28),
    }

    if os.path.exists(colors_file):
        try:
            with open(colors_file, "r") as f:
                data = json.load(f)
                theme["bg"] = hex_to_rgb(data.get("special", {}).get("background", "#1a1624"))
                theme["fg"] = hex_to_rgb(data.get("special", {}).get("foreground", "#ffffff"))
                # Use vibrant color9 or color4
                colors = data.get("colors", {})
                accent_hex = colors.get("color9") or colors.get("color4") or "#cba6f7"
                theme["accent"] = hex_to_rgb(accent_hex)
        except Exception:
            pass

    return theme


def load_layout():
    layout_paths = [
        os.path.expanduser("~/.config/snmenu/layout"),
        os.path.expanduser("~/.config/cpmenu/layout"),
    ]
    for path in layout_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                sys.stderr.write(f"Failed to parse {path}: {e}\n")

    # Default fallback matching the dotfiles configuration
    return [
        {"label": "lock", "action": "hyprlock", "text": "Lock", "icon_char": ""},
        {"label": "suspend", "action": "systemctl suspend", "text": "Suspend", "icon_char": ""},
        {"label": "logout", "action": "hyprctl dispatch exit", "text": "Logout", "icon_char": ""},
        {"label": "shutdown", "action": "systemctl poweroff", "text": "Shutdown", "icon_char": ""},
        {"label": "hibernate", "action": "systemctl hibernate", "text": "Hibernate", "icon_char": ""},
        {"label": "reboot", "action": "systemctl reboot", "text": "Reboot", "icon_char": ""},
    ]


class RadialMenu(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.set_title("snmenu")
        self.set_wmclass("snmenu", "snmenu")
        self.set_role("snmenu")

        self.theme = load_theme()
        self.items = load_layout()
        self.num_items = len(self.items) if self.items else 6

        self.hovered_index = -1
        self.outer_radius = 210.0
        self.inner_radius = 65.0
        self.center_btn_radius = 48.0

        # Transparency setup
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        if HAS_LAYER_SHELL:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_namespace(self, "snmenu")
        else:
            self.fullscreen()
            self.set_decorated(False)

        self.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )

        self.connect("draw", self.on_draw)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("button-press-event", self.on_click)
        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)

    def get_center(self):
        alloc = self.get_allocation()
        return alloc.width / 2.0, alloc.height / 2.0

    def get_slice_index_at(self, x, y):
        cx, cy = self.get_center()
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy)

        if dist < self.inner_radius or dist > self.outer_radius:
            return -1

        # Angle in radians [-pi, pi], with -pi/2 at top (12 o'clock)
        angle = math.atan2(dy, dx)
        phi = (angle + math.pi / 2.0) % (2.0 * math.pi)
        if phi < 0:
            phi += 2.0 * math.pi

        slice_angle = (2.0 * math.pi) / self.num_items
        index = int(phi / slice_angle) % self.num_items
        return index

    def on_motion(self, widget, event):
        new_index = self.get_slice_index_at(event.x, event.y)
        if new_index != self.hovered_index:
            self.hovered_index = new_index
            self.queue_draw()
        return True

    def on_click(self, widget, event):
        if event.button == 1:
            index = self.get_slice_index_at(event.x, event.y)
            if 0 <= index < len(self.items):
                action = self.items[index].get("action", "")
                self.execute_action(action)
                return True
            else:
                # Click outside or in center closes menu
                Gtk.main_quit()
                return True
        elif event.button == 3:  # Right click closes
            Gtk.main_quit()
            return True
        return False

    def on_key(self, widget, event):
        if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            Gtk.main_quit()
            return True
        return False

    def execute_action(self, action):
        if action:
            try:
                subprocess.Popen(action, shell=True)
            except Exception as e:
                sys.stderr.write(f"Failed to execute '{action}': {e}\n")
        Gtk.main_quit()

    def on_draw(self, widget, cr):
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        cx, cy = w / 2.0, h / 2.0

        # 1. Dim background
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.55)
        cr.paint()

        slice_angle = (2.0 * math.pi) / self.num_items

        # 2. Draw Slices
        for i in range(self.num_items):
            item = self.items[i]
            is_hovered = (i == self.hovered_index)

            start_angle = -math.pi / 2.0 + i * slice_angle
            end_angle = start_angle + slice_angle

            # Slice path
            cr.arc(cx, cy, self.outer_radius, start_angle, end_angle)
            cr.arc_negative(cx, cy, self.inner_radius, end_angle, start_angle)
            cr.close_path()

            # Fill color
            if is_hovered:
                r, g, b = self.theme["accent"]
                cr.set_source_rgba(r, g, b, 0.95)
            else:
                r, g, b = self.theme["bg"]
                cr.set_source_rgba(r, g, b, 0.88)
            cr.fill_preserve()

            # Border stroke
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.35)
            cr.set_line_width(2.0)
            cr.stroke()

            # Draw Content (Icon and Text)
            mid_angle = (start_angle + end_angle) / 2.0
            content_r = (self.inner_radius + self.outer_radius) / 2.0
            tx = cx + content_r * math.cos(mid_angle)
            ty = cy + content_r * math.sin(mid_angle)

            # Icon
            icon_char = item.get("icon_char", "")
            label_text = item.get("text", item.get("label", "")).capitalize()

            # Set text color
            if is_hovered:
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            else:
                fr, fg, fb = self.theme["fg"]
                cr.set_source_rgba(fr, fg, fb, 0.92)

            # Icon render
            layout_icon = self.create_pango_layout(icon_char)
            font_desc = Pango.FontDescription("JetBrainsMono Nerd Font 24")
            layout_icon.set_font_description(font_desc)
            _, rect = layout_icon.get_pixel_extents()

            icon_x = tx - rect.width / 2.0
            icon_y = ty - rect.height / 2.0 - 10
            cr.move_to(icon_x, icon_y)
            PangoCairo.show_layout(cr, layout_icon)

            # Label render
            if label_text:
                layout_label = self.create_pango_layout(label_text)
                font_label = Pango.FontDescription("Sans 9")
                layout_label.set_font_description(font_label)
                _, l_rect = layout_label.get_pixel_extents()

                lbl_x = tx - l_rect.width / 2.0
                lbl_y = ty + 14
                cr.move_to(lbl_x, lbl_y)
                PangoCairo.show_layout(cr, layout_label)

        # 3. Center Circle (Inner Hub)
        cr.arc(cx, cy, self.inner_radius - 2.0, 0, 2.0 * math.pi)
        br, bg, bb = self.theme["bg"]
        cr.set_source_rgba(br * 0.7, bg * 0.7, bb * 0.7, 0.98)
        cr.fill_preserve()
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.5)
        cr.set_line_width(3.0)
        cr.stroke()

        # Inner play button circle
        cr.arc(cx, cy, self.center_btn_radius, 0, 2.0 * math.pi)
        cr.set_source_rgba(br * 0.5, bg * 0.5, bb * 0.5, 0.95)
        cr.fill()

        # Draw central play triangle (facing right)
        cr.move_to(cx - 7, cy - 12)
        cr.line_to(cx + 12, cy)
        cr.line_to(cx - 7, cy + 12)
        cr.close_path()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        cr.fill()

        return True


def main():
    # Toggle behavior: if already running, terminate it
    pid_file = "/tmp/snmenu.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 15)  # SIGTERM
            os.remove(pid_file)
            sys.exit(0)
        except (OSError, ValueError):
            pass

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    try:
        app = RadialMenu()
        app.show_all()
        Gtk.main()
    finally:
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except OSError:
                pass


if __name__ == "__main__":
    main()
