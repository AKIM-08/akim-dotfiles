#!/bin/bash
# hypridle: lock session and turn display off after 15 min idle

pidof hyprlock >/dev/null || hyprlock &
hyprctl dispatch dpms off
