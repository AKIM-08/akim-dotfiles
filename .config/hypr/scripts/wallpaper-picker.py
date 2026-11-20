#!/usr/bin/env python3
"""Wallpaper carousel (Super + W).

A fullscreen overlay with the wallpapers as slanted cards: the selected one large in the
middle, the others shrinking and fading toward the edges. Prints the chosen file's path
on stdout and exits; rofi-wallpaper.sh then applies it.

Keys: Left/Right (or H/L, scroll wheel) browse, Enter/Space apply, Esc close.
Mouse: click a side card to bring it to the middle, click the middle card to apply.

Thumbnails are cached in ~/.cache/wallpaper-picker so it opens instantly after the first run.
Needs only python3-pyqt6.
"""

import hashlib
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (QColor, QFont, QImage, QImageReader, QPainter, QPainterPath,
                         QPen, QPolygonF)
from PyQt6.QtWidgets import QApplication, QWidget


def xdg_dir(name: str, fallback: str) -> Path:
    """A user folder in the user's language (xdg-user-dirs): PICTURES is ~/Images in French,
    ~/Bilder in German... Falls back to ~/<fallback> when it isn't set."""
    home = Path.home()
    try:
        for line in (home / ".config" / "user-dirs.dirs").read_text(encoding="utf-8").splitlines():
            if line.startswith(f"XDG_{name}_DIR="):
                value = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(home))
                if value.rstrip("/") != str(home):
                    return Path(value)
    except OSError:
        pass
    return home / fallback


WALL_DIR = xdg_dir("PICTURES", "Pictures") / "wallpapers"
CACHE_DIR = Path.home() / ".cache" / "wallpaper-picker"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
THUMB_WIDTH = 760          # cached thumbnail width (px)
EASE = 0.2                 # animation smoothing per frame (higher = snappier)


def wallpapers() -> list:
    files = [p for p in WALL_DIR.iterdir()
             if p.is_file() and p.suffix.lower() in EXTS and p.name != "current.jpg"]
    return sorted(files, key=lambda p: p.name.lower())


def load_thumb(path: Path):
    """Scaled-down copy of the image, cached on disk by path + size + mtime."""
    try:
        st = path.stat()
    except OSError:
        return None
    key = hashlib.md5(f"{path}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.jpg"
    if cached.is_file():
        img = QImage(str(cached))
        if not img.isNull():
            return img
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > THUMB_WIDTH:
        reader.setScaledSize(size.scaled(THUMB_WIDTH, THUMB_WIDTH * 4, Qt.AspectRatioMode.KeepAspectRatio))
    img = reader.read()
    if img.isNull():
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    img.save(str(cached), "JPG", 88)
    return img


class Picker(QWidget):
    def __init__(self, files: list, start: int):
        super().__init__()
        self.files = files
        self.thumbs = [None] * len(files)
        self.index = start           # target card
        self.pos = float(start)      # animated position
        self.hit = []                # (polygon, index) of drawn cards, for clicks

        self.setWindowTitle("Wallpaper picker")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.anim = QTimer(self)
        self.anim.setInterval(15)
        self.anim.timeout.connect(self.step)

        # Load the cards around the current one first, the rest one per tick
        order = sorted(range(len(files)), key=lambda i: abs(i - start))
        self.pending = order
        self.loader = QTimer(self)
        self.loader.setInterval(0)
        self.loader.timeout.connect(self.load_next)
        for _ in range(min(5, len(order))):
            self.load_next()
        self.loader.start()

    # ------------------------------------------------------------------ loading
    def load_next(self):
        if not self.pending:
            self.loader.stop()
            return
        i = self.pending.pop(0)
        self.thumbs[i] = load_thumb(self.files[i])
        if abs(i - self.pos) < 6:
            self.update()

    # ------------------------------------------------------------------ navigation
    def go(self, i: int):
        self.index = max(0, min(len(self.files) - 1, i))
        if not self.anim.isActive():
            self.anim.start()

    def step(self):
        delta = self.index - self.pos
        if abs(delta) < 0.002:
            self.pos = float(self.index)
            self.anim.stop()
        else:
            self.pos += delta * EASE
        self.update()

    def choose(self):
        print(self.files[self.index], flush=True)
        QApplication.quit()

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            QApplication.quit()
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_H, Qt.Key.Key_Up, Qt.Key.Key_K):
            self.go(self.index - 1)
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_L, Qt.Key.Key_Down, Qt.Key.Key_J, Qt.Key.Key_Tab):
            self.go(self.index + 1)
        elif k == Qt.Key.Key_Home:
            self.go(0)
        elif k == Qt.Key.Key_End:
            self.go(len(self.files) - 1)
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.choose()

    def wheelEvent(self, e):
        d = e.angleDelta()
        step = d.y() or d.x()
        if step:
            self.go(self.index + (1 if step < 0 else -1))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            QApplication.quit()
            return
        p = e.position()
        for poly, i in reversed(self.hit):       # topmost first
            if poly.containsPoint(p, Qt.FillRule.OddEvenFill):
                if i == self.index and abs(self.pos - self.index) < 0.05:
                    self.choose()
                else:
                    self.go(i)
                return
        QApplication.quit()                       # click outside the cards closes

    # ------------------------------------------------------------------ drawing
    def card_geometry(self, d: float):
        """Center, size and opacity of a card at distance d from the middle."""
        W, H = self.width(), self.height()
        h0 = H * 0.36
        a = abs(d)
        scale = 1.0 - 0.36 * min(a, 1.0) - 0.06 * max(0.0, a - 1.0)
        h = h0 * max(scale, 0.35)
        w = h * 16 / 9
        w0 = h0 * 16 / 9
        x = W / 2 + (1 if d >= 0 else -1) * (w0 * 0.62 * min(a, 1.0) + w0 * 0.47 * max(0.0, a - 1.0))
        opacity = 1.0 - 0.3 * min(a, 1.0) - 0.14 * max(0.0, a - 1.0)
        return x, H / 2, w, h, max(opacity, 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))

        self.hit = []
        visible = [i for i in range(len(self.files)) if abs(i - self.pos) < 5.5]
        for i in sorted(visible, key=lambda i: -abs(i - self.pos)):   # far cards first
            d = i - self.pos
            x, y, w, h, opacity = self.card_geometry(d)
            if opacity <= 0.02:
                continue
            slant = h * 0.27
            poly = QPolygonF([QPointF(x - w / 2 + slant / 2, y - h / 2), QPointF(x + w / 2 + slant / 2, y - h / 2),
                              QPointF(x + w / 2 - slant / 2, y + h / 2), QPointF(x - w / 2 - slant / 2, y + h / 2)])
            path = QPainterPath()
            path.addPolygon(poly)
            path.closeSubpath()
            box = QRectF(x - (w + slant) / 2, y - h / 2, w + slant, h)

            p.save()
            p.setOpacity(opacity)
            p.setClipPath(path)
            img = self.thumbs[i]
            if img is not None:
                # cover the card's bounding box, keeping the image's aspect ratio
                src_ratio = img.width() / max(img.height(), 1)
                if src_ratio > box.width() / box.height():
                    sw = img.height() * box.width() / box.height()
                    src = QRectF((img.width() - sw) / 2, 0, sw, img.height())
                else:
                    sh = img.width() * box.height() / box.width()
                    src = QRectF(0, (img.height() - sh) / 2, img.width(), sh)
                p.drawImage(box, img, src)
            else:
                p.fillPath(path, QColor(255, 255, 255, 25))
            p.setClipping(False)
            central = abs(d) < 0.5
            p.setPen(QPen(QColor(255, 255, 255, 230 if central else 70), 2.5 if central else 1))
            p.drawPolygon(poly)
            p.restore()
            self.hit.append((poly, i))

        # File name and hint
        x, y, w, h, _ = self.card_geometry(0)
        p.setOpacity(1.0)
        p.setPen(QColor(255, 255, 255, 235))
        font = QFont("JetBrainsMono Nerd Font", 13)
        font.setBold(True)
        p.setFont(font)
        name = self.files[self.index].stem.replace("-", " ").replace("_", " ")
        p.drawText(QRectF(0, y + h / 2 + 22, self.width(), 30), Qt.AlignmentFlag.AlignHCenter, name)
        p.end()


def main() -> int:
    if not WALL_DIR.is_dir():
        print(f"No wallpaper folder: {WALL_DIR}", file=sys.stderr)
        return 1
    files = wallpapers()
    if not files:
        print(f"No wallpapers in {WALL_DIR}", file=sys.stderr)
        return 1

    current = os.path.realpath(WALL_DIR / "current.jpg")
    start = next((i for i, f in enumerate(files) if os.path.realpath(f) == current), 0)

    app = QApplication(sys.argv)
    app.setDesktopFileName("wallpaper-picker")    # Wayland app id / Hyprland class
    picker = Picker(files, start)
    picker.showFullScreen()
    picker.activateWindow()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
