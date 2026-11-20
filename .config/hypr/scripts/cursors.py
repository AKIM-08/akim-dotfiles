#!/usr/bin/env python3
"""cursors.py - mouse pointer themes: Capitaine, Oreo Spark, Breeze and one in the wallpaper's accent.

    cursors.py set <theme> [size]   switch now and remember it (Settings -> Mouse & keyboard)
    cursors.py restore              apply the remembered theme (Hyprland start)
    cursors.py accent               rebuild the wallpaper-accent pointer if it is the chosen one
                                    (apply-pywal-theme.sh runs this after every wallpaper switch)
    cursors.py build                build Capitaine and Oreo Spark once (install / first use)
    cursors.py get                  print "<theme> <size>"

Themes: capitaine, oreo-spark, breeze, wallpaper (and nordzy, the old default, if installed).

Capitaine (keeferrourke/capitaine-cursors) and Oreo (varlesh/oreo-cursors) ship only their
drawings, so they are built here: the SVGs are rendered with rsvg-convert (librsvg2-bin) and
packed with xcursorgen (x11-apps). Oreo's drawings take their colors as parameters, which is
how the wallpaper-accent theme is made: Oreo in color1 of the current palette. It is written to
one of two theme folders (Wallpaper-Cursors-A / -B) in turn, because Hyprland only reloads a
pointer theme when its name changes.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOME = Path.home()
ICONS = HOME / ".local" / "share" / "icons"
CACHE = HOME / ".cache" / "cursors"
CHOICE = HOME / ".config" / "hypr" / "cursor-theme"
COLORS = HOME / ".cache" / "wal" / "colors.json"

CAPITAINE_URL = "https://github.com/keeferrourke/capitaine-cursors/archive/refs/tags/r4.tar.gz"
OREO_URL = "https://github.com/varlesh/oreo-cursors/archive/refs/heads/master.tar.gz"

THEMES = {                       # choice -> installed theme folder name
    "capitaine": "Capitaine",
    "oreo-spark": "Oreo-Spark",
    "breeze": "breeze_cursors",
    "nordzy": "Nordzy-cursors",
}
DEFAULT = ("capitaine", 28)
SPARK = "#ff50a6"                # Oreo's spark_pink
SIZES = (24, 32, 48, 64)         # rendered pointer sizes (bigger choices pick the closest)


# ------------------------------------------------------------------------------ helpers
def log(msg):
    sys.stderr.write(f"cursors: {msg}\n")


def have(cmd):
    return shutil.which(cmd) is not None


def fetch(url, name) -> Path:
    """Download and unpack a source tarball once; returns the unpacked folder."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name
    if dest.is_dir():
        return dest
    tmp = Path(tempfile.mkdtemp(dir=CACHE))
    archive = tmp / "src.tar.gz"
    with urllib.request.urlopen(url, timeout=60) as r, open(archive, "wb") as out:
        shutil.copyfileobj(r, out)
    with tarfile.open(archive) as t:
        t.extractall(tmp, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(tmp)
    top = next(p for p in tmp.iterdir() if p.is_dir())
    top.rename(dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return dest


def render_all(jobs):
    """jobs: [(svg_path, png_path, size)] rendered in parallel with rsvg-convert."""
    def one(job):
        svg, png, size = job
        png.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(png), str(svg)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        list(pool.map(one, jobs))


def pack(theme_dir: Path, name: str, title: str, specs: dict, aliases: list):
    """specs: cursor -> list of (size, xhot, yhot, png, delay or None). Writes an XCursor theme."""
    tmp = Path(tempfile.mkdtemp(dir=CACHE))
    out = tmp / "cursors"
    out.mkdir()
    for cursor, frames in specs.items():
        cfg = tmp / f"{cursor}.in"
        cfg.write_text("".join(f"{s} {x} {y} {png}" + (f" {d}" if d else "") + "\n" for s, x, y, png, d in frames))
        subprocess.run(["xcursorgen", str(cfg), str(out / cursor)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for link, target in aliases:
        p = out / link
        if not p.exists() and not p.is_symlink() and (out / target).exists():
            p.symlink_to(target)
    (tmp / "index.theme").write_text(f"[Icon Theme]\nName={title}\nComment=Built by cursors.py\n")
    (tmp / "cursors.in").unlink(missing_ok=True)
    for f in tmp.glob("*.in"):
        f.unlink()
    if theme_dir.exists():
        shutil.rmtree(theme_dir)
    theme_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), str(theme_dir))


def read_aliases(path: Path):
    out = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            out.append((parts[0], parts[1]))
    return out


# ------------------------------------------------------------------------------ Capitaine
def build_capitaine():
    src = fetch(CAPITAINE_URL, "capitaine-r4") / "src"
    work = Path(tempfile.mkdtemp(dir=CACHE))
    jobs, specs = [], {}
    for spec in sorted((src / "config" / "static").glob("*.spec")):
        name = spec.stem
        xh, yh = (float(v) for v in spec.read_text().split()[:2])
        specs[name] = []
        for s in SIZES:
            png = work / f"{s}" / f"{name}.png"
            jobs.append((src / "svg" / "dark" / f"{name}.svg", png, s))
            specs[name].append((s, round(xh * s / 24), round(yh * s / 24), png, None))
    for spec in sorted((src / "config" / "animated").glob("*.spec")):
        name = spec.stem
        xh, yh, frames, delay = spec.read_text().split()[:4]
        specs[name] = []
        for s in SIZES:
            for i in range(int(frames)):
                png = work / f"{s}" / f"{name}-{i:02d}.png"
                jobs.append((src / "svg" / "dark" / f"{name}-{i:02d}.svg", png, s))
                specs[name].append((s, round(float(xh) * s / 24), round(float(yh) * s / 24), png, delay))
    jobs = [j for j in jobs if j[0].exists()]
    render_all(jobs)
    specs = {k: [f for f in v if f[3].exists()] for k, v in specs.items()}
    specs = {k: v for k, v in specs.items() if v}
    # Capitaine's alias file is "<link> <target>"
    pack(ICONS / THEMES["capitaine"], "capitaine", "Capitaine", specs, read_aliases(src / "cursor-aliases"))
    shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------------------ Oreo
def build_oreo(theme_dir: Path, title: str, color: str, label="#ffffff", shadow="#000000", shadow_opacity="0.3",
               sizes=SIZES):
    repo = fetch(OREO_URL, "oreo-master")
    base = repo / "generator" / "oreo_base_cursors"
    work = Path(tempfile.mkdtemp(dir=CACHE))
    svgs = work / "svg"
    svgs.mkdir()
    for t in base.glob("*.svg.oreo"):
        data = t.read_text(encoding="utf-8")
        for key, val in (("background", color), ("label", label), ("shadow", shadow),
                         ("shadowopacity", shadow_opacity), ("shadow opacity", shadow_opacity), ("opacity", "1")):
            data = data.replace("{{ " + key + " }}", val)
        (svgs / t.name[:-len(".oreo")]).write_text(data, encoding="utf-8")
    # Hotspots come from the 32 px lines of Oreo's .cursor files: "32 xhot yhot name_32.png [delay]"
    jobs, specs = [], {}
    for cfg in sorted((repo / "src" / "config").glob("*.cursor")):
        frames = []
        for line in cfg.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "32":
                frames.append((float(parts[1]), float(parts[2]), parts[3].rsplit("_", 1)[0], parts[4] if len(parts) > 4 else None))
        if not frames:
            continue
        specs[cfg.stem] = []
        for s in sizes:
            for xh, yh, img, delay in frames:
                png = work / f"{s}" / f"{img}.png"
                if not any(j[1] == png for j in jobs):
                    jobs.append((svgs / f"{img}.svg", png, s))
                specs[cfg.stem].append((s, round(xh * s / 32), round(yh * s / 32), png, delay))
    jobs = [j for j in jobs if j[0].exists()]
    render_all(jobs)
    specs = {k: [f for f in v if f[3].exists()] for k, v in specs.items()}
    specs = {k: v for k, v in specs.items() if v}
    pack(theme_dir, theme_dir.name, title, specs, read_aliases(repo / "src" / "cursorList"))
    shutil.rmtree(work, ignore_errors=True)


def accent_color():
    try:
        return json.loads(COLORS.read_text())["colors"]["color1"]
    except (OSError, ValueError, KeyError):
        return "#5294e2"


def build_accent(size):
    """Oreo in the wallpaper's accent, into whichever of the A/B folders is not in use."""
    current = Path(ICONS / ".wallpaper-cursors-current")
    using = current.read_text().strip() if current.exists() else "Wallpaper-Cursors-B"
    name = "Wallpaper-Cursors-A" if using.endswith("B") else "Wallpaper-Cursors-B"
    # Render the chosen size and its double (HiDPI / zoom), not every size: this runs on every switch
    sizes = tuple(sorted({min(SIZES, key=lambda s: abs(s - size)), 48}))
    build_oreo(ICONS / name, "Wallpaper accent", accent_color(), sizes=sizes)
    current.write_text(name + "\n")
    return name


# ------------------------------------------------------------------------------ applying
def read_choice():
    try:
        theme, size = CHOICE.read_text().split()[:2]
        return theme, int(size)
    except (OSError, ValueError):
        return DEFAULT


def apply(folder: str, size: int):
    subprocess.run(["hyprctl", "setcursor", folder, str(size)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if have("gsettings"):
        for key, val in (("cursor-theme", folder), ("cursor-size", str(size))):
            subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", key, val],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # X11 apps (XWayland) read the default theme from here
    d = HOME / ".icons" / "default"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.theme").write_text(f"[Icon Theme]\nName=Default\nInherits={folder}\n")


def folder_for(theme: str, size: int) -> str:
    if theme == "wallpaper":
        current = ICONS / ".wallpaper-cursors-current"
        if current.exists() and (ICONS / current.read_text().strip()).is_dir():
            return current.read_text().strip()
        return build_accent(size)
    folder = THEMES.get(theme, THEMES["capitaine"])
    if theme == "capitaine" and not (ICONS / folder).is_dir():
        build_capitaine()
    if theme == "oreo-spark" and not (ICONS / folder).is_dir():
        build_oreo(ICONS / folder, "Oreo Spark", SPARK)
    return folder


def check_tools():
    missing = [c for c in ("rsvg-convert", "xcursorgen") if not have(c)]
    if missing:
        log("missing " + ", ".join(missing) + " (sudo apt install librsvg2-bin x11-apps)")
        return False
    return True


def main(argv):
    cmd = argv[0] if argv else "restore"
    if cmd == "get":
        print(*read_choice())
        return 0
    if cmd == "set":
        theme = argv[1] if len(argv) > 1 else DEFAULT[0]
        size = int(argv[2]) if len(argv) > 2 else read_choice()[1]
        if theme not in (*THEMES, "wallpaper"):
            log(f"unknown theme {theme}; use capitaine, oreo-spark, breeze or wallpaper")
            return 2
        CHOICE.parent.mkdir(parents=True, exist_ok=True)
        CHOICE.write_text(f"{theme} {size}\n")
        if theme in ("capitaine", "oreo-spark", "wallpaper") and not check_tools():
            return 1
        apply(folder_for(theme, size), size)
        return 0
    if cmd == "restore":
        theme, size = read_choice()
        try:
            apply(folder_for(theme, size), size)
        except Exception as e:                       # never leave the session without a pointer
            log(f"{theme}: {e}")
            apply("Nordzy-cursors" if (ICONS / "Nordzy-cursors").is_dir() else "Adwaita", size)
        return 0
    if cmd == "accent":
        theme, size = read_choice()
        if theme == "wallpaper" and check_tools():
            apply(build_accent(size), size)
        return 0
    if cmd == "build":
        if not check_tools():
            return 1
        build_capitaine()
        build_oreo(ICONS / THEMES["oreo-spark"], "Oreo Spark", SPARK)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
