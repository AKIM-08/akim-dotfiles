#!/usr/bin/env python3
"""Detect active backlight device and configure SwayNC config.json."""

import glob
import json
import os
import subprocess
import sys


def pick_device():
    # 1. Try brightnessctl output
    try:
        res = subprocess.run(
            ["brightnessctl", "-l", "-c", "backlight", "-m"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                parts = line.split(",")
                if parts and parts[0]:
                    return parts[0].strip()
    except Exception:
        pass

    # 2. Inspect /sys/class/backlight
    candidates = [
        os.path.basename(p)
        for p in glob.glob("/sys/class/backlight/*")
        if os.path.isdir(p)
    ]
    if candidates:
        preferred = (
            "amdgpu_bl",
            "intel_backlight",
            "nvidia",
            "apple_backlight",
            "ddcci",
        )
        for pref in preferred:
            for d in candidates:
                if d.startswith(pref):
                    return d
        for d in candidates:
            if d != "acpi_video0":
                return d
        return candidates[0]

    return "intel_backlight"


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

    device = pick_device()
    if device:
        backlight_cfg["device"] = device
        backlight_cfg["subsystem"] = "backlight"

    tmp_path = f"{config_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
