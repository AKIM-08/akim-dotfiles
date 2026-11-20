#!/usr/bin/env python3
"""boot-screens.py - the boot menu (GRUB) and start-up animation (Plymouth) in your wallpaper.

    boot-screens.py sync     build both from the current wallpaper, its colors and your name, then
                             install them (asks for your password: they live in system folders)
    boot-screens.py reset    back to Debian's boot menu and start-up screen (also stops following)
    boot-screens.py auto-on  follow the wallpaper: asks for your password once to allow this one
                             update without it (a sudo rule for the root-owned copy of
                             boot-screens-root.sh), then syncs
    boot-screens.py auto-off stop following the wallpaper (removes that rule)
    boot-screens.py auto     run after each wallpaper change: when following, waits until the
                             wallpaper stays the same for a minute, then syncs at the lowest priority
                             (--now: right away). What it did: ~/.cache/boot-screens.log
    add --sudo to use sudo in a terminal instead of the graphical password prompt (the installer)

Boot menu: the wallpaper with a dark column on the left holding the entries (accent stripe on the
chosen one), the system name and your name above, a bar counting down to the automatic start.
Start-up: the wallpaper blurred, a spinning ring in the accent color and your name; it also asks
for the disk password when the disk is encrypted.

Images are made here, as you; boot-screens-root.sh only copies them into place and updates
GRUB / the start-up files (Settings -> Wallpaper -> Boot screens).
"""

import json
import math
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HOME = Path.home()
SCRIPTS = Path(__file__).resolve().parent
ROOT_SCRIPT = SCRIPTS / "boot-screens-root.sh"
INSTALLED = "/usr/local/lib/akim-dotfiles/boot-screens-root.sh"     # root-owned copy (auto-on)
AUTO_FLAG = HOME / ".config" / "hypr" / "boot-screens-auto"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
LOG = HOME / ".cache" / "boot-screens.log"      # what the automatic updates did


def log(msg):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        lines = LOG.read_text(encoding="utf-8").splitlines()[-200:] if LOG.exists() else []
        lines.append(time.strftime("%Y-%m-%d %H:%M:%S ") + msg)
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


# ------------------------------------------------------------------------------ inputs
def pictures_dir():
    try:
        p = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3).stdout.strip()
        if p and p != str(HOME):
            return Path(p)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return HOME / "Pictures"


def wallpaper():
    p = pictures_dir() / "wallpapers" / "current.jpg"
    return Path(os.path.realpath(p)) if p.exists() else None


def palette():
    c = {"bg": "#0b0d14", "fg": "#e8ebf4", "accent": "#7aa2f7"}
    try:
        d = json.loads((HOME / ".cache/wal/colors.json").read_text(encoding="utf-8"))
        c = {"bg": d["special"]["background"], "fg": d["special"]["foreground"], "accent": d["colors"]["color1"]}
    except (OSError, ValueError, KeyError):
        pass
    return c


def display_name():
    """The name set on the account (GECOS full name), else the username."""
    pw = pwd.getpwuid(os.getuid())
    full = (pw.pw_gecos or "").split(",")[0].strip()
    return full or pw.pw_name


def system_name():
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("NAME="):
                return line.split("=", 1)[1].strip('"').split()[0]
    except OSError:
        pass
    return "Linux"


def screen_size():
    """The built-in screen's resolution: Hyprland first, then the kernel's list of modes."""
    try:
        mons = json.loads(subprocess.run(["hyprctl", "-j", "monitors"], capture_output=True, text=True, timeout=3).stdout)
        if mons:
            m = next((m for m in mons if m.get("name", "").startswith("eDP")), mons[0])
            return int(m["width"]), int(m["height"])
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        pass
    for modes in sorted(Path("/sys/class/drm").glob("card*-*/modes")):
        try:
            first = modes.read_text().split()[0]
            w, h = first.split("x")
            return int(w), int(re.match(r"\d+", h).group())
        except (OSError, IndexError, ValueError, AttributeError):
            continue
    return 1920, 1080


def font_file(pattern, fallback="DejaVu Sans"):
    for pat in (pattern, fallback):
        try:
            f = subprocess.run(["fc-match", "-f", "%{file}", pat], capture_output=True, text=True, timeout=3).stdout.strip()
            if f and Path(f).exists():
                return f
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------------------ drawing helpers
def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default()
    except OSError:
        return ImageFont.load_default()


def spaced_text(draw, xy, text, font, fill, spacing):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing


def text_image(text, font, fill, pad=4):
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    img = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - l, pad - t), text, font=font, fill=fill)
    return img


# ------------------------------------------------------------------------------ GRUB
def build_grub(out, wall, pal, name, W, H):
    out.mkdir(parents=True)
    acc = rgb(pal["accent"])
    bold = font_file("Inter:weight=800", "DejaVu Sans:bold")
    mono = font_file("JetBrains Mono", "DejaVu Sans Mono")

    bg = cover(Image.open(wall).convert("RGB"), W, H) if wall else Image.new("RGB", (W, H), rgb(pal["bg"]))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = round(W * 0.40)
    d.rectangle((0, 0, col, H), fill=(8, 10, 18, 214))
    d.line((col, 0, col, H), fill=(255, 255, 255, 22), width=1)
    left = round(W * 0.04)
    title = load_font(bold, round(H * 0.062))
    d.text((left, round(H * 0.11)), system_name(), font=title, fill=(255, 255, 255, 255))
    small = load_font(mono, round(H * 0.017))
    spaced_text(d, (left + 2, round(H * 0.11 + H * 0.085)), f"HYPRLAND · {name.upper()}", small, acc + (255,), round(H * 0.003))
    Image.alpha_composite(bg.convert("RGBA"), layer).convert("RGB").save(out / "background.png", optimize=True)

    # Highlight of the chosen entry (nine-patch): accent stripe on the left, light fill
    stripe = max(3, round(H * 0.003))
    pieces = {"w": Image.new("RGBA", (stripe, 1), acc + (255,)), "c": Image.new("RGBA", (1, 1), (255, 255, 255, 20))}
    for p in ("nw", "n", "ne", "e", "se", "s", "sw"):
        pieces[p] = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    for p, img in pieces.items():
        img.save(out / f"select_{p}.png")

    size = round(H * 0.0205)
    font_name = "Unifont Regular 16"
    if mono and shutil.which("grub-mkfont"):
        r = subprocess.run(["grub-mkfont", "-n", "BootMenu", "-s", str(size), "-o", str(out / "font.pf2"), mono],
                           capture_output=True, text=True)
        if r.returncode == 0:
            font_name = f"BootMenu Regular {size}"
    item_h = round(H * 0.044)
    (out / "theme.txt").write_text(f'''# Boot menu from akim-dotfiles (Settings -> Wallpaper -> Boot screens)
title-text: ""
desktop-image: "background.png"
desktop-color: "#000000"
terminal-font: "{font_name}"

+ boot_menu {{
    left = 4%
    top = 30%
    width = 32%
    height = 48%
    item_font = "{font_name}"
    selected_item_font = "{font_name}"
    item_color = "#c9cee0"
    selected_item_color = "#ffffff"
    item_height = {item_h}
    item_padding = {round(H * 0.012)}
    item_spacing = {round(H * 0.004)}
    icon_width = 0
    icon_height = 0
    item_icon_space = 0
    selected_item_pixmap_style = "select_*.png"
    scrollbar = false
}}

+ progress_bar {{
    id = "__timeout__"
    left = 4%
    top = 86%
    width = 32%
    height = {max(3, round(H * 0.0035))}
    fg_color = "{pal['accent']}"
    bg_color = "#2a2f42"
    border_color = "#2a2f42"
    show_text = false
}}

+ label {{
    id = "__timeout__"
    left = 4%
    top = 88%
    width = 32%
    height = {item_h}
    font = "{font_name}"
    color = "#9aa1b8"
    text = "Starting in %d s"
}}
''', encoding="utf-8")


# ------------------------------------------------------------------------------ Plymouth
def build_plymouth(out, wall, pal, name, W, H):
    out.mkdir(parents=True)
    acc = rgb(pal["accent"])
    bold = font_file("Inter:weight=800", "DejaVu Sans:bold")
    mono = font_file("JetBrains Mono", "DejaVu Sans Mono")

    bg = cover(Image.open(wall).convert("RGB"), W, H) if wall else Image.new("RGB", (W, H), rgb(pal["bg"]))
    bg = bg.filter(ImageFilter.GaussianBlur(H * 0.022))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.3)
    bg.save(out / "bg.png", optimize=True)

    # Ring: a 100 degree arc with round ends, drawn large then scaled down for smooth edges
    S = round(H * 0.07)
    k = 4
    big = Image.new("RGBA", (S * k, S * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    t = round(S * 0.075) * k
    d.ellipse((t, t, S * k - t, S * k - t), outline=(255, 255, 255, 40), width=t)
    d.arc((t, t, S * k - t, S * k - t), -90, 10, fill=acc + (255,), width=t)
    r = (S * k - t) / 2 - t / 2
    c = S * k / 2
    for a in (-90, 10):
        x, y = c + r * math.cos(math.radians(a)), c + r * math.sin(math.radians(a))
        d.ellipse((x - t / 2, y - t / 2, x + t / 2, y + t / 2), fill=acc + (255,))
    big.resize((S, S), Image.LANCZOS).save(out / "ring.png")

    text_image(name, load_font(bold, round(H * 0.036)), (255, 255, 255, 255)).save(out / "word.png")
    text_image("Disk password", load_font(mono, round(H * 0.017)), (200, 205, 220, 255)).save(out / "prompt.png")
    b = round(H * 0.011)
    dot = Image.new("RGBA", (b * 4, b * 4), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse((0, 0, b * 4 - 1, b * 4 - 1), fill=(255, 255, 255, 255))
    dot.resize((b, b), Image.LANCZOS).save(out / "bullet.png")
    fw, fh = round(H * 0.3), round(H * 0.04)
    field = Image.new("RGBA", (fw * 2, fh * 2), (0, 0, 0, 0))
    ImageDraw.Draw(field).rounded_rectangle((0, 0, fw * 2 - 1, fh * 2 - 1), radius=fh, fill=(255, 255, 255, 22),
                                            outline=(255, 255, 255, 50), width=2)
    field.resize((fw, fh), Image.LANCZOS).save(out / "field.png")

    (out / "akim.plymouth").write_text("""[Plymouth Theme]
Name=akim-dotfiles
Description=The wallpaper blurred, with a spinning ring (Settings -> Wallpaper -> Boot screens)
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/akim
ScriptFile=/usr/share/plymouth/themes/akim/akim.script
""", encoding="utf-8")
    (out / "akim.script").write_text("""# Start-up animation from akim-dotfiles: blurred wallpaper, spinning ring, your name
W = Window.GetWidth();
H = Window.GetHeight();

bg = Sprite(Image("bg.png").Scale(W, H));
bg.SetZ(-100);

ring_image = Image("ring.png");
ring = Sprite(ring_image);
ring.SetX(W / 2 - ring_image.GetWidth() / 2);
ring.SetY(H / 2 - ring_image.GetHeight() - H * 0.02);

word_image = Image("word.png");
word = Sprite(word_image);
word.SetX(W / 2 - word_image.GetWidth() / 2);
word.SetY(H / 2 + H * 0.01);

# (inside a function, a variable only keeps its value between frames as global.<name>)
global.angle = 0;
fun refresh() {
    global.angle = global.angle + 0.11;
    if (global.angle > 6.2832) global.angle = global.angle - 6.2832;
    ring.SetImage(ring_image.Rotate(global.angle));
}
Plymouth.SetRefreshFunction(refresh);

# Disk password (encrypted disks)
prompt_image = Image("prompt.png");
field_image = Image("field.png");
bullet_image = Image("bullet.png");
prompt = Sprite(prompt_image);
field = Sprite(field_image);
prompt.SetOpacity(0);
field.SetOpacity(0);
prompt.SetX(W / 2 - prompt_image.GetWidth() / 2);
prompt.SetY(word.GetY() + word_image.GetHeight() + H * 0.04);
field.SetX(W / 2 - field_image.GetWidth() / 2);
field.SetY(prompt.GetY() + prompt_image.GetHeight() + H * 0.012);
step = bullet_image.GetWidth() * 2;
most = Math.Int((field_image.GetWidth() - field_image.GetHeight()) / step);
bullets = [];
for (i = 0; i < most; i++) {
    bullets[i] = Sprite(bullet_image);
    bullets[i].SetX(field.GetX() + field_image.GetHeight() / 2 + i * step);
    bullets[i].SetY(field.GetY() + field_image.GetHeight() / 2 - bullet_image.GetHeight() / 2);
    bullets[i].SetZ(10);
    bullets[i].SetOpacity(0);
}

fun display_password(prompt_text, count) {
    ring.SetOpacity(0);
    prompt.SetOpacity(1);
    field.SetOpacity(1);
    for (i = 0; i < most; i++) {
        if (i < count) bullets[i].SetOpacity(1);
        else bullets[i].SetOpacity(0);
    }
}

fun display_normal() {
    ring.SetOpacity(1);
    prompt.SetOpacity(0);
    field.SetOpacity(0);
    for (i = 0; i < most; i++) bullets[i].SetOpacity(0);
}

Plymouth.SetDisplayPasswordFunction(display_password);
Plymouth.SetDisplayNormalFunction(display_normal);
""", encoding="utf-8")


# ------------------------------------------------------------------------------ main
def build(work):
    W, H = screen_size()
    wall, pal, name = wallpaper(), palette(), display_name()
    build_grub(work / "grub", wall, pal, name, W, H)
    build_plymouth(work / "plymouth", wall, pal, name, W, H)
    os.chmod(work, 0o755)
    return f"{W}x{H}"


def run_root(args, how):
    """how: 'pkexec' (graphical password), 'sudo' (terminal), 'auto' (the password-free rule)."""
    if how == "auto":
        cmd = ["nice", "-n", "19", "ionice", "-c", "3", "sudo", "-n", "/bin/sh", INSTALLED] + args
    else:
        cmd = [how, "/bin/sh", str(ROOT_SCRIPT)] + args
    if how != "auto":
        return subprocess.run(cmd).returncode
    r = subprocess.run(cmd, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).strip().splitlines():
        log("  " + line)
    log(f"finished (exit {r.returncode})" + ("" if r.returncode == 0 else
        " - the password-free rule didn't work: turn Follow the wallpaper off and on again in Settings"
        if "password" in r.stderr.lower() else ""))
    return r.returncode


def sync(how):
    work = Path(tempfile.mkdtemp(prefix="boot-screens-", dir="/tmp"))
    try:
        mode = build(work)
        return run_root(["install", str(work), mode], how)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def auto(now=False):
    """After a wallpaper change: sync once the wallpaper has stayed the same for a minute."""
    if not AUTO_FLAG.exists():
        return 0
    if not Path(INSTALLED).exists():
        log("skipped: the password-free rule is missing - turn Follow the wallpaper off and on again")
        return 1
    if not now:
        stamp = RUNTIME / "boot-screens.pending"
        token = f"{os.getpid()}-{time.time()}"
        stamp.write_text(token)
        log("wallpaper changed: updating the boot screens in a minute")
        time.sleep(60)
        try:
            if stamp.read_text() != token:          # another wallpaper came after this one
                return 0
        except OSError:
            return 0
    import fcntl
    with open(RUNTIME / "boot-screens.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        log(f"updating the boot screens from {wallpaper()}")
        try:
            r = sync("auto")
        except Exception as e:                      # noqa: BLE001 - keep the reason in the log
            log(f"failed: {e!r}")
            r = 1
        return r


def main():
    args = [a for a in sys.argv[1:] if a != "--sudo"]
    how = "sudo" if "--sudo" in sys.argv else "pkexec"
    cmd = args[0] if args else ""
    if cmd == "sync":
        sys.exit(sync(how))
    if cmd == "reset":
        r = run_root(["reset"], how)
        if r == 0:
            AUTO_FLAG.unlink(missing_ok=True)
        sys.exit(r)
    if cmd == "auto-on":
        r = run_root(["auto-on", pwd.getpwuid(os.getuid()).pw_name], how)
        if r != 0:
            sys.exit(r)
        AUTO_FLAG.touch()
        sys.exit(sync("auto"))
    if cmd == "auto-off":
        r = run_root(["auto-off"], how)
        if r == 0:
            AUTO_FLAG.unlink(missing_ok=True)
        sys.exit(r)
    if cmd == "auto":
        sys.exit(auto(now="--now" in args))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
