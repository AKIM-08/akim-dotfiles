#!/usr/bin/env python3
"""Extract a 16-color palette from a wallpaper and write pywal cache files."""

import sys
from pathlib import Path

from PIL import Image

WAL_DIR = Path.home() / ".cache" / "wal"


def hex_rgb(r: int, g: int, b: int) -> str:
    return f"{r:02x}{g:02x}{b:02x}"


def luminance(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def extract_colors(image_path: Path) -> list[str]:
    img = Image.open(image_path).convert("RGB")
    img = img.resize((256, 256))
    quantized = img.quantize(colors=32)
    palette = quantized.getpalette()
    if not palette:
        raise RuntimeError("Could not extract palette from image")

    raw_rgbs = []
    for i in range(32):
        r, g, b = palette[i * 3 : i * 3 + 3]
        raw_rgbs.append((r, g, b))

    # Sort by luminance
    raw_rgbs.sort(key=lambda c: luminance(*c))

    # Construct clean dark-mode palette:
    # color0 / background: Deep charcoal tinted with darkest hue
    darkest = raw_rgbs[0]
    bg_r = max(16, min(32, int(darkest[0] * 0.25) + 12))
    bg_g = max(18, min(36, int(darkest[1] * 0.25) + 14))
    bg_b = max(24, min(42, int(darkest[2] * 0.25) + 20))

    # Foreground: Clean bright white/cream
    fg_r, fg_g, fg_b = 218, 224, 238

    # Pick 6 distinct vibrant midtones for colors 1-6
    accents = raw_rgbs[4:28]
    step = max(1, len(accents) // 6)
    picked = [accents[i * step] for i in range(6)]

    colors = [hex_rgb(bg_r, bg_g, bg_b)]
    for r, g, b in picked:
        # Boost saturation/vibrancy slightly for dark background
        colors.append(hex_rgb(min(255, max(40, r)), min(255, max(40, g)), min(255, max(40, b))))
    colors.append(hex_rgb(fg_r, fg_g, fg_b))

    # Bright variants (colors 8-15)
    colors.append(hex_rgb(bg_r + 20, bg_g + 20, bg_b + 25))
    for r, g, b in picked:
        colors.append(hex_rgb(min(255, r + 30), min(255, g + 30), min(255, b + 30)))
    colors.append(hex_rgb(245, 247, 255))

    return colors[:16]


def write_hyprland_conf(colors: list[str], wallpaper: Path) -> None:
    lines = [
        "# Fallback palette extracted from wallpaper (pywal unavailable)",
        f"$real_wallpaper = {wallpaper}",
        f"$background = rgb({colors[0]})",
        f"$foreground = rgb({colors[7]})",
    ]
    for i, color in enumerate(colors):
        lines.append(f"$color{i} = rgb({color})")
    text = "\n".join(lines) + "\n"
    (WAL_DIR / "colors-hyprland.conf").write_text(text)
    (WAL_DIR / "colors-hyprland.hl").write_text(text)


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


def write_cpmenu_layout(colors: list[str]) -> None:
    content = f"""[
    {{
        "label": "lock",
        "action": "hyprlock",
        "text": "Lock",
        "icon_char": "",
        "show_label": true,
        "color": "#{colors[0]}",
        "hover_color": "#{colors[4]}"
    }},
    {{
        "label": "suspend",
        "action": "systemctl suspend",
        "text": "Suspend",
        "icon_char": "",
        "show_label": true,
        "color": "#{colors[0]}",
        "hover_color": "#{colors[4]}"
    }},
    {{
        "label": "logout",
        "action": "hyprctl dispatch exit",
        "text": "Logout",
        "icon_char": "",
        "show_label": true,
        "color": "#{colors[0]}",
        "hover_color": "#{colors[4]}"
    }},
    {{
        "label": "shutdown",
        "action": "systemctl poweroff",
        "text": "Shutdown",
        "icon_char": "",
        "show_label": true,
        "color": "#{colors[0]}",
        "hover_color": "#{colors[1]}"
    }},
    {{
        "label": "hibernate",
        "action": "systemctl hibernate",
        "text": "Hibernate",
        "icon_char": "",
        "show_label": true,
        "color": "#{colors[0]}",
        "hover_color": "#{colors[4]}"
    }},
    {{
        "label": "reboot",
        "action": "systemctl reboot",
        "text": "Reboot",
        "icon_char": "",
        "show_label": true,
        "color": "#{colors[0]}",
        "hover_color": "#{colors[2]}"
    }}
]"""
    (WAL_DIR / "cpmenu-layout").write_text(content)


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
    write_cpmenu_layout(colors)

    return 0


if __name__ == "__main__":
    sys.exit(main())
