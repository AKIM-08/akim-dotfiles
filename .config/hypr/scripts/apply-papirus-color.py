#!/usr/bin/env python3
import json
import math
import os
import subprocess
from pathlib import Path

# Couleurs prédéfinies de papirus-folders et leurs valeurs RGB approximatives
PAPIRUS_COLORS = {
    "red": (244, 67, 54),
    "pink": (233, 30, 99),
    "violet": (156, 39, 176),
    "indigo": (103, 58, 183),
    "blue": (33, 150, 243),
    "cyan": (3, 169, 244),
    "darkcyan": (0, 188, 212),
    "teal": (0, 150, 136),
    "green": (76, 175, 80),
    "yellow": (255, 235, 59),
    "orange": (255, 152, 0),
    "brown": (121, 85, 72),
    "grey": (158, 158, 158),
    "bluegrey": (96, 125, 139),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "nord": (136, 192, 208)
}

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def color_distance(c1, c2):
    # Distance euclidienne simple dans l'espace RGB
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

def main():
    wal_colors_path = Path.home() / ".cache" / "wal" / "colors.json"
    if not wal_colors_path.exists():
        return

    with open(wal_colors_path, 'r') as f:
        wal_data = json.load(f)
    
    # Prendre la couleur d'accentuation (color4 ou color2 par exemple)
    # color4 est souvent la couleur "bleu/accent" principale de pywal
    accent_hex = wal_data["colors"]["color4"]
    accent_rgb = hex_to_rgb(accent_hex)

    # Trouver la couleur Papirus la plus proche
    closest_color_name = "blue"
    min_dist = float('inf')

    for name, rgb in PAPIRUS_COLORS.items():
        dist = color_distance(accent_rgb, rgb)
        if dist < min_dist:
            min_dist = dist
            closest_color_name = name

    # Appliquer avec papirus-folders (silencieusement)
    try:
        subprocess.run(["papirus-folders", "-C", closest_color_name, "--theme", "Papirus-Dark"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


if __name__ == "__main__":
    main()
