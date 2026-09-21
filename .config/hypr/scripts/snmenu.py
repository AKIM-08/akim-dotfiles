#!/usr/bin/env python3
"""
snmenu.py - Lightweight GTK3/Cairo circular radial power menu
- Sleek hollow donut ring with 6 sector slices
- Dynamic wallpaper colors from pywal (~/.cache/wal/colors.json)
- Hover expansion effect with wallpaper accent color (CS:GO / wlogout radial style)
- Crisp typography and Nerd Font icons
- Instant ESC / click-outside dismiss
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
    from gi.repository import Gtk, Gdk, Pango, PangoCairo
    import cairo
except ImportError as e:
    sys.stderr.write(f"Error loading GTK3/Cairo: {e}\n")
    sys.exit(1)

# Wayland overlay support via GtkLayerShell if present
HAS_LAYER_SHELL = False
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
    HAS_LAYER_SHELL = True
except Exception:
    HAS_LAYER_SHELL = False


def hex_to_rgb(hex_str, default=(0.1, 0.1, 0.1)):
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
        "bg": (0.10, 0.08, 0.14),
        "fg": (1.0, 1.0, 1.0),
        "accent": (0.88, 0.29, 0.61),
        "overlay": (0.0, 0.0, 0.0, 0.60),
        "wedge_bg": (0.13, 0.10, 0.17, 0.90),
        "center_bg": (0.08, 0.06, 0.11, 0.85),
    }

    if os.path.exists(colors_file):
        try:
            with open(colors_file, "r") as f:
                data = json.load(f)
                bg_hex = data.get("special", {}).get("background", "#14121a")
                fg_hex = data.get("special", {}).get("foreground", "#ffffff")
                colors = data.get("colors", {})
                accent_hex = colors.get("color1") or colors.get("color9") or "#e04b9b"

                bg_rgb = hex_to_rgb(bg_hex)
                theme["bg"] = bg_rgb
                theme["wedge_bg"] = (bg_rgb[0], bg_rgb[1], bg_rgb[2], 0.90)
                theme["center_bg"] = (bg_rgb[0] * 0.7, bg_rgb[1] * 0.7, bg_rgb[2] * 0.7, 0.85)
                theme["overlay"] = (bg_rgb[0] * 0.3, bg_rgb[1] * 0.3, bg_rgb[2] * 0.3, 0.60)
                theme["fg"] = hex_to_rgb(fg_hex)
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

    return [
        {"label": "lock", "action": "hyprlock", "text": "Lock", "icon_char": ""},
        {"label": "suspend", "action": "loginctl lock-session; systemctl suspend", "text": "Suspend", "icon_char": ""},
        {"label": "logout", "action": "hyprctl dispatch exit", "text": "Logout", "icon_char": ""},
        {"label": "shutdown", "action": "systemctl poweroff", "text": "Shutdown", "icon_char": ""},
        {"label": "hibernate", "action": "loginctl lock-session; systemctl hibernate", "text": "Hibernate", "icon_char": ""},
        {"label": "reboot", "action": "systemctl reboot", "text": "Reboot", "icon_char": ""},
    ]


class RadialMenu(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.set_title("snmenu")
        self.set_wmclass("snmenu", "snmenu")

        self.theme = load_theme()
        self.items = load_layout()
        self.num_items = len(self.items) if self.items else 6

        self.hovered_index = -1
        self.outer_radius = 235.0
        self.inner_radius = 78.0

        # Enable true RGBA transparency
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

        # Center is hollow hole, outside is outer screen
        if dist < self.inner_radius or dist > (self.outer_radius + 30.0):
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
            window = self.get_window()
            if window:
                if new_index >= 0:
                    cursor = Gdk.Cursor.new_from_name(window.get_display(), "pointer")
                else:
                    cursor = Gdk.Cursor.new_from_name(window.get_display(), "default")
                window.set_cursor(cursor)
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
                # Click outside the donut or in the center dismisses menu
                Gtk.main_quit()
                return True
        elif event.button == 3:
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

    def draw_slice(self, cr, cx, cy, index, is_hovered, slice_angle):
        item = self.items[index]
        start_angle = -math.pi / 2.0 + index * slice_angle
        end_angle = start_angle + slice_angle

        # Hovered wedge pops outward like Picture 3
        outer_r = self.outer_radius + 22.0 if is_hovered else self.outer_radius
        inner_r = self.inner_radius

        cr.arc(cx, cy, outer_r, start_angle, end_angle)
        cr.arc_negative(cx, cy, inner_r, end_angle, start_angle)
        cr.close_path()

        if is_hovered:
            ar, ag, ab = self.theme["accent"]
            cr.set_source_rgba(ar, ag, ab, 0.96)
        else:
            br, bg, bb, ba = self.theme["wedge_bg"]
            cr.set_source_rgba(br, bg, bb, ba)
        cr.fill_preserve()

        # Outline border
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.40)
        cr.set_line_width(1.5)
        cr.stroke()

        # Content position (Icon & Text)
        mid_angle = (start_angle + end_angle) / 2.0
        content_r = (inner_r + outer_r) / 2.0
        tx = cx + content_r * math.cos(mid_angle)
        ty = cy + content_r * math.sin(mid_angle)

        icon_char = item.get("icon_char", "")
        label_text = item.get("text", item.get("label", "")).capitalize()

        # Crisp white text & icons in both states
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)

        # Draw icon
        layout_icon = self.create_pango_layout(icon_char)
        font_desc = Pango.FontDescription("JetBrainsMono Nerd Font 24")
        layout_icon.set_font_description(font_desc)
        _, rect = layout_icon.get_pixel_extents()

        icon_x = tx - rect.width / 2.0
        icon_y = ty - rect.height / 2.0 - 8
        cr.move_to(icon_x, icon_y)
        PangoCairo.show_layout(cr, layout_icon)

        # Draw label underneath
        if label_text:
            layout_label = self.create_pango_layout(label_text)
            font_label = Pango.FontDescription("JetBrainsMono Nerd Font Bold 9.5")
            layout_label.set_font_description(font_label)
            _, l_rect = layout_label.get_pixel_extents()

            lbl_x = tx - l_rect.width / 2.0
            lbl_y = ty + 16
            cr.move_to(lbl_x, lbl_y)
            PangoCairo.show_layout(cr, layout_label)

    def on_draw(self, widget, cr):
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        cx, cy = w / 2.0, h / 2.0

        # 1. Dimmed background
        or_, og, ob, oa = self.theme["overlay"]
        cr.set_source_rgba(or_, og, ob, oa)
        cr.paint()

        slice_angle = (2.0 * math.pi) / self.num_items

        # 2. Draw non-hovered slices first
        for i in range(self.num_items):
            if i != self.hovered_index:
                self.draw_slice(cr, cx, cy, i, False, slice_angle)

        # 3. Draw the popped-out hovered slice on TOP of everything (Picture 3)
        if 0 <= self.hovered_index < self.num_items:
            self.draw_slice(cr, cx, cy, self.hovered_index, True, slice_angle)

        # 4. Draw center circle background
        c_r, c_g, c_b, c_a = self.theme["center_bg"]
        cr.arc(cx, cy, self.inner_radius, 0, 2.0 * math.pi)
        cr.set_source_rgba(c_r, c_g, c_b, c_a)
        cr.fill_preserve()
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.40)
        cr.set_line_width(1.5)
        cr.stroke()

        # 5. Draw outer base circle border
        cr.arc(cx, cy, self.outer_radius, 0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.40)
        cr.set_line_width(1.5)
        cr.stroke()

        return True


def main():
    pid_file = "/tmp/snmenu.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 15)
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
