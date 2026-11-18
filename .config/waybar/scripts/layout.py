#!/usr/bin/env python3
"""Build the live Waybar config and style from a theme + a screen edge.

Usage:
    layout.py                         rebuild from the saved choice
    layout.py --theme zen             switch theme, keep the position
    layout.py --position left         move the bar, keep the theme
    layout.py --size large            bar thickness: compact, normal, large
    layout.py --gap 12                space between the bar and windows (0-40 px)
    layout.py --get                   print "<theme> <position> <size>"
    layout.py --program               print what runs the bar: waybar, dock (Waybar + auto-hide) or island

Inputs (in ~/.config/waybar/themes/):
    modules.json            module definitions shared by every theme
    <theme>/config-<theme>  the theme's layout and overrides (JSON, comments allowed)
    <theme>/style-<theme>.css

Keys starting with "x-" are build hints, never written to the final config:
    "x-vertical": {...}     merged over the config when the bar is on the left/right edge
    "x-floating": false     the bar touches the screen edge (no outer margins)
    "x-dot-workspaces": true  workspace buttons are drawn as dots/bars; their margins are
                            scaled with the bar size so they keep their shape
    "x-positions": [...]    edges the theme supports; another saved edge is replaced by the first
    "x-autohide": true      dock: hidden until the pointer touches its edge (scripts/dock-autohide.py);
                            windows use the whole screen
    "x-taskbar-scale": 2    app icons this many times the normal icon size
    "x-scale-ids": {"#a, #b": 1.3}   font size of these selectors relative to the bar's text
    "x-program": "island"   the bar is not Waybar but ~/.config/hypr/scripts/island.py

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


def theme_hints(theme: str) -> dict:
    """The theme's own x- build hints (from its config file, not modules.json)."""
    try:
        cfg = load_jsonc(THEMES / theme / f"config-{theme}")
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in cfg.items() if k.startswith("x-")}


def program(theme: str) -> str:
    hints = theme_hints(theme)
    if hints.get("x-program") == "island":
        return "island"
    return "dock" if hints.get("x-autohide") else "waybar"


def size_css(size: dict, dots: bool, scaled: dict = None, dot_margins=None) -> str:
    css = ("\n/* ---- Bar size (added by scripts/layout.py) ---- */\n"
           "* { font-size: %dpx; }\n"
           "#custom-launcher { font-size: %dpx; }\n" % (size["font"], size["logo"]))
    for selector, scale in (scaled or {}).items():
        css += "%s { font-size: %dpx; }\n" % (selector, round(size["font"] * float(scale)))
    if dots:
        mh, mv = dot_margins or (size["dot"], size["dot"])
        css += ("window#waybar.pos-top #workspaces button, window#waybar.pos-bottom #workspaces button "
                "{ margin-top: %dpx; margin-bottom: %dpx; }\n"
                "window#waybar.pos-left #workspaces button, window#waybar.pos-right #workspaces button "
                "{ margin-left: %dpx; margin-right: %dpx; }\n" % (mh, mh, mv, mv))
    return css


def build(theme: str, position: str, size_name: str, gap: int = WINDOW_GAP_BAR) -> None:
    vertical = position in ("left", "right")
    size = SIZES[size_name]
    cfg = merge(load_jsonc(THEMES / "modules.json"), load_jsonc(THEMES / theme / f"config-{theme}"))

    if vertical:
        cfg = merge(cfg, cfg.get("x-vertical", {}))
    floating = cfg.get("x-floating", True)
    dots = cfg.get("x-dot-workspaces", False)
    autohide = cfg.get("x-autohide", False)
    taskbar_scale = float(cfg.get("x-taskbar-scale", 1))
    scaled = cfg.get("x-scale-ids", {})
    cfg = {k: v for k, v in cfg.items() if not k.startswith("x-")}

    # Icons follow the bar size (one step smaller on side bars, where many apps stack up)
    if isinstance(cfg.get("tray"), dict):
        cfg["tray"]["icon-size"] = size["icon"]
    if isinstance(cfg.get("wlr/taskbar"), dict):
        cfg["wlr/taskbar"]["icon-size"] = round(size["icon"] * taskbar_scale) - (1 if vertical else 0)

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
    if autohide:
        # Drawn over the windows instead of reserving space; dock-autohide.py shows it (SIGUSR1)
        cfg["exclusive"] = False
        cfg["start_hidden"] = True

    write_if_changed(WAYBAR / "config", json.dumps(cfg, indent=4, ensure_ascii=False) + "\n")
    style = (THEMES / theme / f"style-{theme}.css").read_text(encoding="utf-8")
    # Waybar stretches workspace buttons to the tallest module; next to big dock icons the
    # margins must absorb the app button's size (icon + its 10px/8px padding) to keep 8px dots
    dot_margins = None
    if dots and taskbar_scale != 1:
        icon = round(size["icon"] * taskbar_scale)
        dot_margins = (max(size["dot"], (icon + 10 - 8) // 2), max(size["dot"], (icon - 1 + 8 - 8) // 2))
    write_if_changed(WAYBAR / "style.css", style + size_css(size, dots, scaled, dot_margins))

    gaps = [gap if side == position and not autohide else WINDOW_GAP_EDGE
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
        if arg == "--program":
            print(program(state["theme"]) if (THEMES / state["theme"]).is_dir() else "waybar")
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

    allowed = theme_hints(state["theme"]).get("x-positions")
    if allowed and state["position"] not in allowed:
        state["position"] = allowed[0]          # e.g. the island only exists at the top

    if state["size"] not in SIZES:
        print(f"Unknown size '{state['size']}'. Use: {', '.join(SIZES)}", file=sys.stderr)
        return 1

    build(state["theme"], state["position"], state["size"], int(state.get("gap", WINDOW_GAP_BAR)))
    STATE.write_text(json.dumps(state) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
