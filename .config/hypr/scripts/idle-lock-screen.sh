#!/bin/bash
# idle.py (hypridle): lock the session and turn the display off

pidof hyprlock >/dev/null || hyprlock &
hyprctl dispatch dpms off
