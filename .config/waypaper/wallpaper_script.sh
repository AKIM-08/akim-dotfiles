#!/bin/bash
# Called by Waypaper after the wallpaper changes (hyprpaper backend).
exec "$HOME/.config/hypr/scripts/apply-pywal-theme.sh" "$1"
