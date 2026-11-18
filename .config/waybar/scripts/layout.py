#!/usr/bin/env python3
"""Build the live Waybar config and style from a theme + a screen edge.

Usage:
    layout.py                         rebuild from the saved choice
    layout.py --theme zen             switch theme, keep the position
    layout.py --position left         move the bar, keep the theme
    layout.py --size large            bar thickness: compact, normal, large
    layout.py --gap 12                space between the bar and windows (0-40 px)
    layout.py --get                   print "<theme> <position> <size>"

Inputs (in ~/.config/waybar/themes/):
    modules.json            module definitions shared by every theme
    <theme>/config-<theme>  the theme's layout and overrides (JSON, comments allowed)
    <theme>/style-<theme>.css

Keys starting with "x-" are build hints, never written to the final config:
    "x-vertical": {...}     merged over the config when the bar is on the left/right edge
    "x-floating": false     the bar touches the screen edge (no outer margins)
    "x-dot-workspaces": true  workspace buttons are drawn as dots/bars; their margins are
                            scaled with the bar size so they keep their shape

Outputs:
    ~/.config/waybar/config, ~/.config/waybar/style.css
    ~/.config/hypr/waybar-gaps.hl   (smaller window gap on the bar's side)
    ~/.config/waybar/layout.json    (the saved choice)
"""

import json
import re
import sys
from pathlib import Path

HOME = Path.home()
WAYBAR = HOME / ".config" / "waybar"
THEMES = WAYBAR / "themes"
STATE = WAYBAR / "layout.json"
GAPS_FILE = HOME / ".config" / "hypr" / "waybar-gaps.hl"

POSITIONS = ("top", "bottom", "left", "right")
OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
DEFAULT = {"theme": "capsule", "position": "top", "size": "normal", "gap": 12}

# Bar thickness. Text and icons scale; on a side bar this is its width, on top/bottom its height.
#   font: base text size   icon: tray/taskbar icons   logo: Debian logo
#   dot: vertical margin that keeps dot/bar workspaces 8px thick at this text size
SIZES = {
    "compact": {"font": 11, "icon": 13, "logo": 14, "dot": 4},
    "normal":  {"font": 13, "icon": 15, "logo": 16, "dot": 5},
    "large":   {"font": 15, "icon": 18, "logo": 19, "dot": 6},
}

BAR_MARGIN_EDGE = 6    # floating bar: space between bar and screen edge
BAR_MARGIN_ALONG = 10  # floating bar: space at both ends of the bar
WINDOW_GAP_BAR = 12    # default Hyprland gap between windows and the bar (state "gap")
WINDOW_GAP_EDGE = 20   # Hyprland gap on the other three sides


def load_jsonc(path: Path):
    """JSON with // and /* */ comments and trailing commas (Waybar's config dialect)."""
    text = path.read_text(encoding="utf-8")
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    cleaned = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    data = json.loads(cleaned)
    return data[0] if isinstance(data, list) else data


def merge(base: dict, over: dict) -> dict:
    result = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def themes() -> list:
    return sorted(p.name for p in THEMES.iterdir()
                  if (p / f"config-{p.name}").is_file() and (p / f"style-{p.name}.css").is_file())


def read_state() -> dict:
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        return {**DEFAULT, **{k: state[k] for k in DEFAULT if k in state}}
    except (OSError, ValueError):
        return dict(DEFAULT)


def write_if_changed(path: Path, content: str) -> bool:
    try:
        if path.read_text(encoding="utf-8") == content:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def size_css(size: dict, dots: bool) -> str:
    css = ("\n/* ---- Bar size (added by scripts/layout.py) ---- */\n"
           "* { font-size: %dpx; }\n"
           "#custom-launcher { font-size: %dpx; }\n" % (size["font"], size["logo"]))
    if dots:
        m = size["dot"]
        css += ("window#waybar.pos-top #workspaces button, window#waybar.pos-bottom #workspaces button "
                "{ margin-top: %dpx; margin-bottom: %dpx; }\n"
                "window#waybar.pos-left #workspaces button, window#waybar.pos-right #workspaces button "
                "{ margin-left: %dpx; margin-right: %dpx; }\n" % (m, m, m, m))
    return css


def build(theme: str, position: str, size_name: str, gap: int = WINDOW_GAP_BAR) -> None:
    vertical = position in ("left", "right")
    size = SIZES[size_name]
    cfg = merge(load_jsonc(THEMES / "modules.json"), load_jsonc(THEMES / theme / f"config-{theme}"))

    if vertical:
        cfg = merge(cfg, cfg.get("x-vertical", {}))
    floating = cfg.get("x-floating", True)
    dots = cfg.get("x-dot-workspaces", False)
    cfg = {k: v for k, v in cfg.items() if not k.startswith("x-")}

    # Icons follow the bar size (one step smaller on side bars, where many apps stack up)
    if isinstance(cfg.get("tray"), dict):
        cfg["tray"]["icon-size"] = size["icon"]
    if isinstance(cfg.get("wlr/taskbar"), dict):
        cfg["wlr/taskbar"]["icon-size"] = size["icon"] - (1 if vertical else 0)

    cfg["layer"] = "top"
    cfg["position"] = position
    cfg["name"] = f"pos-{position}"          # CSS: window#waybar.pos-left etc.
    cfg["reload_style_on_change"] = True
    for side in POSITIONS:
        if not floating or side == OPPOSITE[position]:
            margin = 0
        elif side == position:
            margin = BAR_MARGIN_EDGE
        else:
            margin = BAR_MARGIN_ALONG
        cfg[f"margin-{side}"] = margin
    cfg.pop("margin", None)

    write_if_changed(WAYBAR / "config", json.dumps(cfg, indent=4, ensure_ascii=False) + "\n")
    style = (THEMES / theme / f"style-{theme}.css").read_text(encoding="utf-8")
    write_if_changed(WAYBAR / "style.css", style + size_css(size, dots))

    gaps = [gap if side == position else WINDOW_GAP_EDGE
            for side in ("top", "right", "bottom", "left")]      # Hyprland order
    write_if_changed(GAPS_FILE,
                     "# Generated by ~/.config/waybar/scripts/layout.py: smaller gap on the bar's side\n"
                     "general {\n    gaps_out = %d, %d, %d, %d\n}\n" % tuple(gaps))


def main(argv: list) -> int:
    state = read_state()
    args = iter(argv)
    for arg in args:
        if arg == "--get":
            print(state["theme"], state["position"], state["size"])
            return 0
        if arg == "--theme":
            state["theme"] = next(args, "")
        elif arg == "--position":
            state["position"] = next(args, "")
        elif arg == "--size":
            state["size"] = next(args, "")
        elif arg == "--gap":
            try:
                state["gap"] = max(0, min(40, int(next(args, ""))))
            except ValueError:
                print("--gap needs a number of pixels (0-40)", file=sys.stderr)
                return 2
        else:
            print(__doc__, file=sys.stderr)
            return 2

    available = themes()
    if state["theme"] not in available:
        print(f"Unknown theme '{state['theme']}'. Available: {', '.join(available)}", file=sys.stderr)
        return 1
    if state["position"] not in POSITIONS:
        print(f"Unknown position '{state['position']}'. Use: {', '.join(POSITIONS)}", file=sys.stderr)
        return 1

    if state["size"] not in SIZES:
        print(f"Unknown size '{state['size']}'. Use: {', '.join(SIZES)}", file=sys.stderr)
        return 1

    build(state["theme"], state["position"], state["size"], int(state.get("gap", WINDOW_GAP_BAR)))
    STATE.write_text(json.dumps(state) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
