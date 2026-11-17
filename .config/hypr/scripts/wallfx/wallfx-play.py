#!/usr/bin/env python3
"""Play the wallfx transition from the old wallpaper to the new one.

    wallfx-play.py <old image> <new image> <reveal map> [--fallback TYPE] [--duration S]
    wallfx-play.py --check          exit 0 if GTK layer shell + OpenGL are available

A fullscreen layer surface on the "bottom" layer (above the wallpaper, below windows and
Waybar) first shows the old wallpaper. Once it is on screen, awww switches to the new
wallpaper underneath without a transition; the layer then reveals the new image following
the reveal map (see wallfx-map.py) in a fragment shader and closes. The GPU does the work:
one fullscreen quad per frame for ~1.8 s.

If anything fails, the wallpaper is set with a normal awww transition (--fallback type).
"""

import os
import subprocess
import sys
import time

# GTK's GL context on Wayland is EGL; PyOpenGL must look its functions up there
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

DURATION = 1.8
AWWW_DEFAULT = ["--transition-fps", "60", "--filter", "Lanczos3", "--resize", "crop"]


def awww(image: str, transition: str, wait: bool = False):
    cmd = ["awww", "img", image, "--transition-type", transition] + AWWW_DEFAULT
    if transition != "none":
        cmd += ["--transition-step", "90", "--transition-angle", "30"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if wait:
        proc.wait()
    return proc


def parse(argv):
    opts = {"fallback": "outer", "duration": DURATION}
    pos = []
    it = iter(argv)
    for a in it:
        if a == "--fallback":
            opts["fallback"] = next(it, "outer")
        elif a == "--duration":
            opts["duration"] = float(next(it, DURATION))
        else:
            pos.append(a)
    return pos, opts


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell
    from OpenGL import GL
    from PIL import Image
    AVAILABLE = True
except (ImportError, ValueError) as err:
    AVAILABLE = False
    IMPORT_ERROR = err


VERTEX = """
#version 330 core
out vec2 uv;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);   // fullscreen triangle
    uv = vec2(p.x, 1.0 - p.y);                               // images are stored top row first
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

FRAGMENT = """
#version 330 core
in vec2 uv;
out vec4 color;
uniform sampler2D old_img;
uniform sampler2D new_img;
uniform sampler2D reveal_map;
uniform float t;
void main() {
    vec4 m = texture(reveal_map, uv);
    float when = m.r;                       // 0..1: when this pixel switches
    float edge = m.g;                       // 1 on the character's outline
    float k = smoothstep(when - 0.035, when + 0.035, t);
    vec3 c = mix(texture(old_img, uv).rgb, texture(new_img, uv).rgb, k);
    // the outline is drawn as a bright stroke, then fades while the world fills in
    float traced = smoothstep(when - 0.01, when + 0.01, t) * edge;
    float fade = 1.0 - smoothstep(0.40, 0.65, t);
    c = mix(c, vec3(1.0), traced * fade * 0.9);
    color = vec4(c, 1.0);
}
"""


def cover_bytes(path: str, w: int, h: int, mode: str = "RGB") -> bytes:
    img = Image.open(path)
    if hasattr(img, "draft"):
        img.draft("RGB", (w, h))
    img = img.convert(mode)
    scale = max(w / img.width, h / img.height)
    nw, nh = max(w, round(img.width * scale)), max(h, round(img.height * scale))
    img = img.resize((nw, nh), Image.Resampling.BILINEAR)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h)).tobytes()


class Player:
    def __init__(self, old: str, new: str, reveal: str, fallback: str, duration: float):
        self.new, self.fallback, self.duration = new, fallback, duration
        self.start = None
        self.switch = None          # awww process for the instant switch underneath
        self.done_at = None
        self.failed = False

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geo, scale = monitor.get_geometry(), monitor.get_scale_factor()
        self.w, self.h = geo.width * scale, geo.height * scale
        self.images = [cover_bytes(old, self.w, self.h), cover_bytes(new, self.w, self.h),
                       cover_bytes(reveal, self.w, self.h)]

        win = Gtk.Window()
        GtkLayerShell.init_for_window(win)
        GtkLayerShell.set_namespace(win, "wallfx")
        GtkLayerShell.set_layer(win, GtkLayerShell.Layer.BOTTOM)
        GtkLayerShell.set_monitor(win, monitor)
        for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(win, edge, True)
        GtkLayerShell.set_exclusive_zone(win, -1)          # also cover the area under Waybar
        try:
            GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
        except AttributeError:
            GtkLayerShell.set_keyboard_interactivity(win, False)

        area = Gtk.GLArea()
        area.set_required_version(3, 3)
        area.set_has_depth_buffer(False)
        area.connect("realize", self.on_realize)
        area.connect("render", self.on_render)
        area.add_tick_callback(self.on_tick)
        win.add(area)
        self.area, self.win = area, win
        win.show_all()
        GLib.timeout_add_seconds(8, self.give_up)          # never hang around

    # ---------------------------------------------------------------- GL setup
    def on_realize(self, area):
        area.make_current()
        if area.get_error() is not None:
            return self.fail("no OpenGL context")
        try:
            def shader(kind, src):
                s = GL.glCreateShader(kind)
                GL.glShaderSource(s, src)
                GL.glCompileShader(s)
                if not GL.glGetShaderiv(s, GL.GL_COMPILE_STATUS):
                    raise RuntimeError(GL.glGetShaderInfoLog(s))
                return s
            prog = GL.glCreateProgram()
            GL.glAttachShader(prog, shader(GL.GL_VERTEX_SHADER, VERTEX))
            GL.glAttachShader(prog, shader(GL.GL_FRAGMENT_SHADER, FRAGMENT))
            GL.glLinkProgram(prog)
            if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
                raise RuntimeError(GL.glGetProgramInfoLog(prog))
            self.prog = prog
            self.vao = GL.glGenVertexArrays(1)

            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            self.textures = GL.glGenTextures(3)
            for unit, (tex, data) in enumerate(zip(self.textures, self.images)):
                GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
                GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGB8, self.w, self.h, 0,
                                GL.GL_RGB, GL.GL_UNSIGNED_BYTE, data)
            self.images = None                              # free the CPU copies
            GL.glUseProgram(prog)
            for unit, name in enumerate(("old_img", "new_img", "reveal_map")):
                GL.glUniform1i(GL.glGetUniformLocation(prog, name), unit)
            self.t_loc = GL.glGetUniformLocation(prog, "t")
        except Exception as e:                              # bad driver, shader error, ...
            self.fail(f"OpenGL setup failed: {e}")

    # ---------------------------------------------------------------- frames
    def progress(self) -> float:
        if self.start is None:
            return 0.0
        return min(1.0, (time.monotonic() - self.start) / self.duration)

    def on_render(self, area, _ctx):
        if self.failed:
            return True
        GL.glClearColor(0, 0, 0, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glUseProgram(self.prog)
        GL.glUniform1f(self.t_loc, self.progress())
        for unit, tex in enumerate(self.textures):
            GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        if self.switch is None:
            # The old wallpaper is now covered by this layer: switch awww underneath
            self.switch = False
            GLib.timeout_add(60, self.begin)
        return True

    def begin(self):
        self.switch = awww(self.new, "none")
        self.start = time.monotonic()
        return False

    def on_tick(self, area, _clock):
        if self.failed:
            return False
        area.queue_render()
        if self.start is not None and self.progress() >= 1.0:
            if self.switch and self.switch.poll() is not None:
                if self.done_at is None:
                    self.done_at = time.monotonic()
                elif time.monotonic() - self.done_at > 0.12:
                    Gtk.main_quit()
                    return False
        return True

    # ---------------------------------------------------------------- failure
    def fail(self, why: str):
        if self.failed:
            return
        self.failed = True
        print(f"wallfx: {why}; using an awww transition instead", file=sys.stderr)
        awww(self.new, self.fallback)
        GLib.idle_add(Gtk.main_quit)

    def give_up(self):
        if not self.failed:
            if not self.switch:
                awww(self.new, "none", wait=True)
            Gtk.main_quit()
        return False


def main(argv) -> int:
    if argv[:1] == ["--check"]:
        return 0 if AVAILABLE else 3
    pos, opts = parse(argv)
    if len(pos) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    old, new, reveal = pos
    if not AVAILABLE:
        print(f"wallfx: unavailable ({IMPORT_ERROR}); using an awww transition", file=sys.stderr)
        awww(new, opts["fallback"], wait=True)
        return 3
    try:
        Player(old, new, reveal, opts["fallback"], opts["duration"])
    except Exception as e:
        print(f"wallfx: {e}; using an awww transition", file=sys.stderr)
        awww(new, opts["fallback"], wait=True)
        return 1
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
