#!/usr/bin/env python3

import glob
import json
import os
import sys


def pick_device():
    candidates = [
        os.path.basename(p)
        for p in glob.glob("/sys/class/backlight/*")
        if os.path.isdir(p)
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    preferred_prefixes = (
        "intel_backlight",
        "amdgpu_",
        "nvidia",
        "apple_backlight",
        "ddcci",
    )
    for d in candidates:
        if d.startswith(preferred_prefixes):
            return d

    for d in candidates:
        if d != "acpi_video0":
            return d

    return candidates[0]


def main():
    config_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.expanduser("~/.config/swaync/config.json")
    )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return 0

    widget_cfg = data.setdefault("widget-config", {})
    backlight_cfg = widget_cfg.setdefault("backlight", {})
    if backlight_cfg.get("device"):
        return 0

    device = pick_device()
    if not device:
        return 0

    backlight_cfg["subsystem"] = backlight_cfg.get("subsystem") or "backlight"
    backlight_cfg["device"] = device

    tmp_path = f"{config_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
