#!/usr/bin/env bash
# wallfx-setup.sh - Install the optional character detection for wallpaper transitions
#
# Creates ~/.local/share/wallfx/ with a private Python environment (onnxruntime, numpy,
# pillow; ~60 MB) and two models (~170 MB each): isnet-anime for anime characters and
# isnet-general-use as a second opinion for painterly/realistic art. Then builds the reveal
# maps for all wallpapers in the background. Without it, transitions use pixel colonies.
#
#   wallfx-setup.sh            install
#   wallfx-setup.sh --remove   delete the environment, model and cached maps

set -euo pipefail

DATA="$HOME/.local/share/wallfx"
VENV="$DATA/venv"
MODEL="$DATA/isnet-anime.onnx"
MODEL_URL="https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx"
GENERAL="$DATA/isnet-general-use.onnx"
GENERAL_URL="https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

notify() { notify-send -u low "Wallpaper transitions" "$1" 2>/dev/null || true; echo "--> $1"; }

if [ "${1:-}" = "--remove" ]; then
    rm -rf -- "$HOME/.local/share/wallfx" "$HOME/.cache/wallfx"
    notify "Character detection removed"
    exit 0
fi

mkdir -p "$DATA"

if [ ! -x "$VENV/bin/python" ]; then
    notify "Creating the Python environment..."
    python3 -m venv "$VENV" || { notify "python3-venv is missing: sudo apt install python3-venv"; exit 1; }
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet onnxruntime numpy pillow

if [ ! -s "$MODEL" ]; then
    notify "Downloading the anime character model (~170 MB)..."
    curl -fL --retry 3 -o "$MODEL.part" "$MODEL_URL"
    mv "$MODEL.part" "$MODEL"
fi
if [ ! -s "$GENERAL" ]; then
    notify "Downloading the general model for non-anime art (~170 MB)..."
    curl -fL --retry 3 -o "$GENERAL.part" "$GENERAL_URL"
    mv "$GENERAL.part" "$GENERAL"
fi

notify "Ready. Building transition maps for your wallpapers in the background."
# Maps built earlier without the model said "no character"; let the model decide now
find "$HOME/.cache/wallfx" -name '*-nosubject' -delete 2>/dev/null || true
nohup nice -n 19 "$VENV/bin/python" "$HERE/wallfx-map.py" precache >/dev/null 2>&1 &
