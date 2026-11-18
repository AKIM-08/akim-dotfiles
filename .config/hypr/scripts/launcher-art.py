#!/usr/bin/env python3
"""Crop the wallpaper for the launcher's art panel (Super + Q).

    launcher-art.py <wallpaper> <output.jpg>

Writes a small portrait crop (PANEL_W x PANEL_H at 2x) of the wallpaper's center, so Rofi
loads a ~100 KB image instead of the full wallpaper every time the launcher opens.
"""

import sys

from PIL import Image

# 3:4 portrait. Rofi scales it to the panel's height (url(..., height)); at that size it is
# wider than the 280px panel whenever the launcher is >= ~374px tall (it is ~460), so it
# always covers the panel instead of tiling
PANEL_W, PANEL_H = 300, 400
SCALE = 2


def main(src: str, dst: str) -> int:
    w, h = PANEL_W * SCALE, PANEL_H * SCALE
    img = Image.open(src)
    img.draft("RGB", (w * 2, h * 2))
    img = img.convert("RGB")
    # Scale so the crop's height fits, then take a centered portrait slice
    scale = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * scale)), max(h, round(img.height * scale))), Image.Resampling.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    img.crop((left, top, left + w, top + h)).save(dst, "JPEG", quality=88)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
