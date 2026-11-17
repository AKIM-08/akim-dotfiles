#!/usr/bin/env python3
"""Reveal maps for the wallfx wallpaper transition.

A reveal map is a small RGB PNG (MAP_W x MAP_H, the wallpaper cropped to 16:9):
    R = when the pixel appears, 0 (first) .. 255 (last)
    G = 255 on the character's outline (drawn as a bright stroke), else 0

Two kinds:
    subject   the wallpaper has a character: its outline is traced first, then the
              character fills in, then the world grows outward from it.
              Needs the optional isnet-anime model (wallfx-setup.sh).
    colonies  no character / no model: blocky pixel colonies spread from random seeds.

Commands:
    wallfx-map.py get <image>       print a map path for the image (instant; builds the
                                    cheap colonies map if needed and, when the model is
                                    installed, starts the subject map in the background)
    wallfx-map.py build <image>     build the best map now (slow with the model)
    wallfx-map.py precache          build maps for every wallpaper in ~/Pictures/wallpapers
    wallfx-map.py status            show which transition each wallpaper gets, and why
    wallfx-map.py force <image>     use the character outline even if detection was unsure

Maps are cached in ~/.cache/wallfx/ by image path, size and modification time.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MAP_VERSION = 2          # bump to rebuild every cached map
MAP_W, MAP_H = 960, 540
HOME = Path.home()
CACHE = HOME / ".cache" / "wallfx"
DATA = HOME / ".local" / "share" / "wallfx"
MODEL = DATA / "isnet-anime.onnx"
# Optional second opinion for characters the anime model can't see (painterly, realistic,
# 3D art). Same family/input as the anime model, different normalization mean.
GENERAL_MODEL = DATA / "isnet-general-use.onnx"
MODEL_MEANS = {"anime": (0.485, 0.456, 0.406), "general": (0.5, 0.5, 0.5)}
WALL_DIR = HOME / "Pictures" / "wallpapers"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# A "character" covers a sensible share of the picture (close-up portraits can fill most of
# it); below MIN_CONFIDENCE the model isn't sure anything is there. Otherwise: colonies.
SUBJECT_MIN, SUBJECT_MAX = 0.01, 0.95
MIN_CONFIDENCE = 0.2     # real characters scored down to ~0.29; empty scenes ~0.01-0.17


# --------------------------------------------------------------------------- helpers
def key_for(path: Path) -> str:
    st = path.stat()
    raw = f"{MAP_VERSION}|{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    return hashlib.md5(raw.encode()).hexdigest()


def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale and center-crop to w x h (same framing as awww --resize crop)."""
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    nw, nh = max(w, round(img.width * scale)), max(h, round(img.height * scale))
    img = img.resize((nw, nh), Image.Resampling.BILINEAR)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def open_image(path: Path, w: int, h: int) -> Image.Image:
    img = Image.open(path)
    img.draft("RGB", (w * 2, h * 2))          # fast JPEG downscale while decoding
    return cover(img, w, h)


def smooth_noise(h: int, w: int, cells: int, rng) -> np.ndarray:
    """Soft random field in [0, 1]: a coarse random grid, bilinearly upscaled."""
    gh, gw = max(2, h // cells), max(2, w // cells)
    grid = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8))
    return np.asarray(grid.resize((w, h), Image.Resampling.BICUBIC), dtype=np.float32) / 255.0


def shift_any(m: np.ndarray, r: int, grow: bool) -> np.ndarray:
    """Binary dilation (grow=True) or erosion with a (2r+1)^2 square, via shifts."""
    out = m.copy()
    p = np.pad(m, r, mode="edge")
    h, w = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            win = p[r + dy:r + dy + h, r + dx:r + dx + w]
            out = (out | win) if grow else (out & win)
    return out


def layer_distance(m: np.ndarray, grow: bool, limit: int) -> np.ndarray:
    """Distance (in steps of 1px, 8-connected) from the mask boundary.

    grow=True: for pixels outside m, how many dilations until reached.
    grow=False: for pixels inside m, how many erosions until removed."""
    dist = np.zeros(m.shape, dtype=np.float32)
    cur = m.copy()
    for step in range(1, limit + 1):
        nxt = shift_any(cur, 1, grow)
        changed = nxt != cur
        if not changed.any():
            break
        dist[changed] = step
        cur = nxt
    if grow:
        dist[~cur] = limit           # never reached
    return dist


def save_map(path: Path, reveal: np.ndarray, outline: np.ndarray) -> None:
    r = np.clip(reveal * 255.0, 0, 255).astype(np.uint8)
    g = np.clip(outline * 255.0, 0, 255).astype(np.uint8)
    rgb = np.dstack([r, g, np.zeros_like(r)])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}.png")
    Image.fromarray(rgb, "RGB").save(tmp)
    os.replace(tmp, path)


# --------------------------------------------------------------------------- maps
def colonies_map(seed: int) -> tuple:
    """Pixel colonies: blocks appear in waves around a few random seeds."""
    rng = np.random.default_rng(seed)
    block = 12
    bh, bw = MAP_H // block + 1, MAP_W // block + 1
    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
    n = 9
    sy, sx = rng.random(n) * bh, rng.random(n) * bw
    start = rng.random(n) * 0.35
    speed = 0.9 + rng.random(n) * 0.6
    diag = float(np.hypot(bh, bw))
    t = np.full((bh, bw), np.inf, dtype=np.float32)
    for i in range(n):
        d = np.hypot(yy - sy[i], xx - sx[i]) / diag / speed[i]
        t = np.minimum(t, start[i] + d)
    t += rng.random((bh, bw)).astype(np.float32) * 0.12      # ragged colony edges
    t = (t - t.min()) / max(float(t.max() - t.min()), 1e-6)
    t = 0.02 + 0.96 * t
    big = np.kron(t, np.ones((block, block), dtype=np.float32))[:MAP_H, :MAP_W]
    return big, np.zeros_like(big)


def subject_map(mask: np.ndarray, seed: int) -> tuple:
    """Outline traced first (around the centroid, starting at the top), then the
    character fills from its edge inward, then the world grows outward from it."""
    rng = np.random.default_rng(seed)
    m = mask > 0.5
    h, w = m.shape

    band = shift_any(m, 2, True) & ~shift_any(m, 2, False)          # outline stroke

    ys, xs = np.nonzero(m)
    cy, cx = ys.mean(), xs.mean()
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = (np.arctan2(xx - cx, -(yy - cy)) / (2 * np.pi)) % 1.0    # 0 at the top, clockwise

    # Distances at half resolution (fast), then back to full size
    small = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize((w // 2, h // 2)), dtype=np.uint8) > 127
    d_in = layer_distance(small, grow=False, limit=200)
    d_out = layer_distance(small, grow=True, limit=600)
    up = lambda a: np.array(Image.fromarray(a).resize((w, h), Image.Resampling.BILINEAR), dtype=np.float32)
    d_in, d_out = up(d_in), up(d_out)
    d_in /= max(float(d_in.max()), 1.0)
    d_out /= max(float(d_out.max()), 1.0)

    noise = smooth_noise(h, w, 40, rng)
    reveal = np.where(m, 0.30 + 0.18 * d_in, 0.50 + 0.46 * d_out ** 0.85 + 0.04 * (noise - 0.5))
    reveal = np.where(band, 0.02 + 0.26 * ang, reveal)
    return np.clip(reveal, 0.0, 1.0), band.astype(np.float32)


# --------------------------------------------------------------------------- model
def installed_models() -> list:
    """Model names in the order they are tried (the anime model first)."""
    return [n for n, f in (("anime", MODEL), ("general", GENERAL_MODEL)) if f.is_file()]


def run_model(name: str, framed: Image.Image) -> np.ndarray:
    """Raw 1024x1024 prediction (0..1) of one model for the framed wallpaper."""
    import onnxruntime as ort    # only in the wallfx venv
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = max(1, (os.cpu_count() or 2) // 2)    # leave CPU for the user
    path = MODEL if name == "anime" else GENERAL_MODEL
    sess = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
    x = np.asarray(framed.resize((1024, 1024), Image.Resampling.LANCZOS), dtype=np.float32)
    x = x / max(float(x.max()), 1e-6)
    x = x - np.array(MODEL_MEANS[name], dtype=np.float32)          # std is 1.0 for both
    x = np.expand_dims(x.transpose(2, 0, 1), 0).astype(np.float32)
    return sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]


def otsu(values: np.ndarray) -> float:
    """Threshold that best splits values (0..1) into two groups."""
    hist, edges = np.histogram(values, bins=64, range=(0.0, 1.0))
    hist = hist.astype(np.float64)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1)
    m1 = (np.sum(hist * centers) - np.cumsum(hist * centers)) / np.maximum(w1, 1)
    return float(centers[int(np.argmax(w0 * w1 * (m0 - m1) ** 2))])


def segment(path: Path, force: bool = False):
    """(character mask MAP_H x MAP_W in 0..1, or None; a short explanation).

    The explanation ends with "(models: ...)" so a later run knows whether a newly
    installed model deserves a second look."""
    img = Image.open(path)
    img.draft("RGB", (2048, 2048))
    framed = cover(img, MAP_W * 2, MAP_H * 2)        # same framing as the wallpaper
    names = installed_models()
    tag = f"(models: {'+'.join(names)})"
    tried, best = [], None
    for name in names:
        pred = run_model(name, framed)
        confidence = float(pred.max())
        tried.append(f"{name} {confidence:.2f}")
        if best is None or confidence > best[1]:
            best = (pred, confidence, name)
        if confidence < MIN_CONFIDENCE:
            continue
        norm = (pred - pred.min()) / max(float(pred.max() - pred.min()), 1e-6)
        mask = np.array(Image.fromarray((norm * 255).astype(np.uint8)).resize((MAP_W, MAP_H), Image.Resampling.BILINEAR),
                        dtype=np.float32) / 255.0
        share = float((mask > 0.5).mean())
        if SUBJECT_MIN <= share <= SUBJECT_MAX:
            return mask, f"{name} model: covers {share:.0%}, confidence {confidence:.2f}"
        tried[-1] += f" but covers {share:.0%}"

    if force and best is not None:
        # The user says there is a character: take the clearest split of the best guess
        pred, confidence, name = best
        norm = (pred - pred.min()) / max(float(pred.max() - pred.min()), 1e-6)
        mask = np.array(Image.fromarray((norm * 255).astype(np.uint8)).resize((MAP_W, MAP_H), Image.Resampling.BILINEAR),
                        dtype=np.float32) / 255.0
        cut = otsu(mask)
        mask = (mask > cut).astype(np.float32)
        share = float(mask.mean())
        if 0.002 <= share <= 0.98:
            return mask, f"forced, {name} model: covers {share:.0%}"
        return None, f"nothing usable even when forced ({', '.join(tried)}) {tag}"

    best_conf = best[1] if best else 0.0
    return None, f"model unsure (confidence {best_conf:.2f} < {MIN_CONFIDENCE}; tried {', '.join(tried)}) {tag}"


def have_model() -> bool:
    # find_spec doesn't import onnxruntime (slow); this runs on every wallpaper switch
    import importlib.util
    return bool(installed_models()) and importlib.util.find_spec("onnxruntime") is not None


# --------------------------------------------------------------------------- commands
def paths_for(image: Path) -> dict:
    k = key_for(image)
    return {"subject": CACHE / f"{k}-subject.png", "colonies": CACHE / f"{k}-colonies.png",
            "none": CACHE / f"{k}-nosubject"}


def decided_no_subject(marker: Path) -> bool:
    """A "no character" verdict still holds. It is retried when a model installed since then
    hasn't seen the image yet, or when its recorded confidence now passes MIN_CONFIDENCE
    (e.g. after the threshold was lowered)."""
    if not marker.exists():
        return False
    import re
    text = marker.read_text()
    seen = re.search(r"\(models: ([a-z+]*)\)", text)
    seen_models = set(seen.group(1).split("+")) if seen else {"anime"}
    if set(installed_models()) - seen_models:
        return False
    found = re.search(r"model unsure \(confidence ([0-9.]+)", text)
    return not (found and float(found.group(1)) >= MIN_CONFIDENCE)


def build(image: Path, force: bool = False) -> Path:
    p = paths_for(image)
    seed = int(key_for(image)[:8], 16)
    if p["subject"].is_file():
        return p["subject"]
    if have_model() and (force or not decided_no_subject(p["none"])):
        mask, why = segment(image, force)
        if mask is not None:
            reveal, outline = subject_map(mask, seed)
            save_map(p["subject"], reveal, outline)
            p["none"].unlink(missing_ok=True)
            return p["subject"]
        p["none"].parent.mkdir(parents=True, exist_ok=True)
        p["none"].write_text(why + "\n")
    if not p["colonies"].is_file():
        reveal, outline = colonies_map(seed)
        save_map(p["colonies"], reveal, outline)
    return p["colonies"]


def get(image: Path) -> Path:
    p = paths_for(image)
    if p["subject"].is_file():
        return p["subject"]
    if have_model() and not decided_no_subject(p["none"]):
        # Too slow to wait for: use colonies now, have the character map ready next time
        subprocess.Popen(["nice", "-n", "19", sys.executable, __file__, "build", str(image)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    if not p["colonies"].is_file():
        reveal, outline = colonies_map(int(key_for(image)[:8], 16))
        save_map(p["colonies"], reveal, outline)
    return p["colonies"]


def precache() -> None:
    import fcntl
    CACHE.mkdir(parents=True, exist_ok=True)
    lock = open(CACHE / ".precache.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return                                    # another precache is running
    for f in sorted(WALL_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in EXTS and f.name != "current.jpg":
            try:
                build(f)
            except Exception as e:                # one bad image must not stop the rest
                print(f"wallfx: {f.name}: {e}", file=sys.stderr)


def status() -> None:
    model = have_model()
    print(f"character model: {'installed' if model else 'not installed (run wallfx-setup.sh)'}\n")
    for f in sorted(WALL_DIR.iterdir()):
        if not (f.is_file() and f.suffix.lower() in EXTS and f.name != "current.jpg"):
            continue
        p = paths_for(f)
        if p["subject"].is_file():
            state = "outline"
        elif decided_no_subject(p["none"]):
            state = "colonies  - no character: " + p["none"].read_text().strip()
        elif model:
            state = "pending   - not analysed yet (precache runs at login)"
        else:
            state = "colonies"
        print(f"  {f.name:40.40}  {state}")


def find_image(arg: str):
    """The image path, also when the name's capitals differ (kuri.jpeg -> Kuri.jpeg)."""
    path = Path(arg).expanduser()
    if path.is_file():
        return path.resolve()
    folder = path.parent if str(path.parent) not in ("", ".") or path.parent.is_dir() else WALL_DIR
    for candidate in (folder, WALL_DIR):
        if candidate.is_dir():
            for f in candidate.iterdir():
                if f.name.lower() == path.name.lower() and f.is_file():
                    return f.resolve()
    print(f"No such image: {path} (check the name with: ls {WALL_DIR})", file=sys.stderr)
    return None


def main(argv: list) -> int:
    if len(argv) >= 1 and argv[0] == "precache":
        precache()
        return 0
    if len(argv) >= 1 and argv[0] == "status":
        status()
        return 0
    if len(argv) == 2 and argv[0] == "force":
        image = find_image(argv[1])
        if image is None:
            return 1
        if not have_model():
            print("The character model isn't installed: run wallfx-setup.sh first", file=sys.stderr)
            return 1
        out = build(image, force=True)
        print(out if out.name.endswith("-subject.png") else f"No character found at all in {image.name}")
        return 0
    if len(argv) == 2 and argv[0] in ("get", "build"):
        image = find_image(argv[1])
        if image is None:
            return 1
        print(get(image) if argv[0] == "get" else build(image))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
