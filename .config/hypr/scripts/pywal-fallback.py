#!/usr/bin/env python3
"""Extract a 16-color palette from a wallpaper and write pywal cache files."""

import sys
from pathlib import Path

from PIL import Image

WAL_DIR = Path.home() / ".cache" / "wal"


def hex_rgb(r: int, g: int, b: int) -> str:
    return f"{r:02x}{g:02x}{b:02x}"


def extract_colors(image_path: Path) -> list[str]:
    img = Image.open(image_path).convert("RGB")
    img = img.resize((256, 256))
    quantized = img.quantize(colors=16)
    palette = quantized.getpalette()
    if not palette:
        raise RuntimeError("Could not extract palette from image")

    colors: list[str] = []
    for i in range(16):
        r, g, b = palette[i * 3 : i * 3 + 3]
        colors.append(hex_rgb(r, g, b))
    return colors


def write_hyprland_conf(colors: list[str], wallpaper: Path) -> None:
    lines = [
        "# Fallback palette extracted from wallpaper (pywal unavailable)",
        f"$real_wallpaper = {wallpaper}",
        f"$background = rgb({colors[0]})",
        f"$foreground = rgb({colors[7]})",
    ]
    for i, color in enumerate(colors):
        lines.append(f"$color{i} = rgb({color})")
    (WAL_DIR / "colors-hyprland.conf").write_text("\n".join(lines) + "\n")


def write_waybar_css(colors: list[str]) -> None:
    lines = [
        "/* Palette extracted from wallpaper (pywal unavailable) */",
        f"@define-color foreground #{colors[7]};",
        f"@define-color background #{colors[0]};",
        f"@define-color cursor #{colors[7]};",
    ]
    for i, color in enumerate(colors):
        lines.append(f"@define-color color{i} #{color};")
    (WAL_DIR / "colors-waybar.css").write_text("\n".join(lines) + "\n")


def write_kitty_conf(colors: list[str]) -> None:
    names = [
        "color0", "color1", "color2", "color3", "color4", "color5", "color6", "color7",
        "color8", "color9", "color10", "color11", "color12", "color13", "color14", "color15",
    ]
    lines = [
        "# Palette extracted from wallpaper (pywal unavailable)",
        f"background #{colors[0]}",
        f"foreground #{colors[7]}",
        f"cursor #{colors[7]}",
    ]
    for name, color in zip(names, colors):
        lines.append(f"{name} #{color}")
    (WAL_DIR / "colors-kitty.conf").write_text("\n".join(lines) + "\n")


def write_gtk_css(colors: list[str]) -> None:
    content = f"""/* Palette extracted from wallpaper (pywal unavailable) */
@define-color theme_bg_color #{colors[0]};
@define-color theme_fg_color #{colors[7]};
@define-color theme_base_color #{colors[0]};
@define-color theme_text_color #{colors[7]};
@define-color theme_selected_bg_color #{colors[4]};
@define-color theme_selected_fg_color #{colors[7]};
@define-color accent_bg_color #{colors[4]};
@define-color accent_fg_color #{colors[0]};
"""
    (WAL_DIR / "colors-gtk.css").write_text(content)


def write_rofi_dark(colors: list[str]) -> None:
    content = f"""* {{
    background-color: #{colors[0]};
    text-color:       #{colors[7]};
    border-color:     #{colors[4]};
    selected-normal-background: #{colors[4]};
    selected-normal-foreground: #{colors[0]};
    active-background: #{colors[2]};
    active-foreground: #{colors[0]};
    urgent-background: #{colors[1]};
    urgent-foreground: #{colors[7]};
}}
"""
    (WAL_DIR / "colors-rofi-dark").write_text(content)


def write_colors_sh(colors: list[str], wallpaper: Path) -> None:
    lines = [
        "# Palette extracted from wallpaper (pywal unavailable)",
        f"wallpaper='{wallpaper}'",
    ]
    for i, color in enumerate(colors):
        lines.append(f"color{i}='#{color}'")
    lines.append(f"background='#{colors[0]}'")
    lines.append(f"foreground='#{colors[7]}'")
    (WAL_DIR / "colors.sh").write_text("\n".join(lines) + "\n")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <wallpaper>", file=sys.stderr)
        return 1

    wallpaper = Path(sys.argv[1]).expanduser()
    if not wallpaper.is_file():
        print(f"Wallpaper not found: {wallpaper}", file=sys.stderr)
        return 1

    WAL_DIR.mkdir(parents=True, exist_ok=True)
    colors = extract_colors(wallpaper)

    write_hyprland_conf(colors, wallpaper)
    write_waybar_css(colors)
    write_kitty_conf(colors)
    write_rofi_dark(colors)
    write_gtk_css(colors)
    write_colors_sh(colors, wallpaper)

    return 0


if __name__ == "__main__":
    sys.exit(main())
