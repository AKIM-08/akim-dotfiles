#!/usr/bin/env bash
# keybinds.sh — Interactive Shortcuts Cheatsheet & Documentation for Hyprland
# Toggle support: SUPER+G opens and closes the menu

set -euo pipefail

# If cheatsheet is already open, toggle it off!
if pgrep -f "rofi.*keybinds.rasi" >/dev/null; then
    pkill -f "rofi.*keybinds.rasi"
    exit 0
fi

SHORTCUTS=(
    "󰌌  SUPER + G                  󰄾  Shortcuts Documentation / Cheatsheet (Toggle)"
    "󰞷  SUPER + Return             󰄾  Open Terminal (Kitty)"
    "󰀻  SUPER + Q                  󰄾  Application Launcher (Rofi - Toggle)"
    "󰖟  SUPER + B                  󰄾  Open Web Browser (Firefox)"
    "󰉋  SUPER + F                  󰄾  File Manager (Nautilus)"
    "󰙯  SUPER + D                  󰄾  Discord"
    "󰅌  SUPER + V                  󰄾  Clipboard History Manager (Rofi - Toggle)"
    "󰈆  SUPER + Escape             󰄾  Power Menu (snmenu CS:GO Radial)"
    "󰂚  SUPER + N                  󰄾  Notification Center (SwayNC)"
    "󰄀  SUPER + P                  󰄾  Screenshot & Recording Menu (Rofi)"
    "󰄀  SUPER + SHIFT + P          󰄾  Screenshot Region (Draw Box)"
    "󰍹  SUPER + ALT + P            󰄾  Screenshot Full Screen"
    "󰑋  SUPER + SHIFT + R          󰄾  Screen Recording (Start / Stop Toggle)"
    "󰄀  Print                      󰄾  Quick Screenshot"
    "󰆍  SUPER + S                  󰄾  Scratchpad Workspace (Show / Hide)"
    "󰆍  SUPER + SHIFT + S          󰄾  Send / Retrieve Active Window to Scratchpad"
    "󰖲  SUPER + Space / Tab        󰄾  Toggle Floating / Tiling Window"
    "󰖲  SUPER + T                  󰄾  Float & Center Window (Toggle)"
    "󰖲  SUPER + SHIFT + Space      󰄾  Center Window on Screen"
    "󰍹  SUPER + SHIFT + F          󰄾  Toggle Fullscreen Window"
    "󰅖  SUPER + A                  󰄾  Close Active Window"
    "󰍃  SUPER + M                  󰄾  Exit Hyprland Session"
    "󰘸  SUPER + J                  󰄾  Toggle Split Layout (Vertical / Horizontal)"
    "󰮔  SUPER + Arrows             󰄾  Move Window Focus (Left / Right / Up / Down)"
    "󰪹  SUPER + SHIFT + Arrows     󰄾  Move Window Position"
    "󰩨  SUPER + CTRL + Arrows/HJKL 󰄾  Resize Active Window"
    "󰍽  SUPER + LMB / RMB Drag     󰄾  Move / Resize Window with Mouse"
    "󱂬  SUPER + 1 - 10 (& to à)    󰄾  Switch to Workspace 1 to 10 (AZERTY)"
    "󱂬  SUPER + SHIFT + 1 - 10     󰄾  Move Window to Workspace 1 to 10"
    "󱂬  SUPER + ALT + 1 - 10       󰄾  Switch to Workspace 11 to 20"
    "󱂬  SUPER + Mouse Scroll       󰄾  Cycle Through Workspaces"
    "󰒓  SUPER + F12                󰄾  Power Mode Selector (Performance / Balanced / Saver)"
    "󰅶  SUPER + C                  󰄾  Caffeine Mode Toggle (Prevent Sleep / Lock)"
    "󰸉  SUPER + W                  󰄾  Wallpaper Picker (Rofi)"
    "󰸉  SUPER + ALT + Right        󰄾  Next Wallpaper + Auto-Theme Update"
    "󰸉  SUPER + ALT + Left         󰄾  Previous Wallpaper + Auto-Theme Update"
    "󱄄  SUPER + SHIFT + T          󰄾  Waybar Theme Selector (Wofi)"
    "󱊦  SUPER + X                  󰄾  Emoji & Character Picker"
    "󰕾  Fn + Volume Up / Down      󰄾  Volume Control (with OSD)"
    "󰃟  Fn + Brightness Up / Down  󰄾  Screen Brightness Control (with OSD)"
    "󰝚  Fn + Audio Next / Prev     󰄾  Media Player Control (playerctl)"
)

printf "%s\n" "${SHORTCUTS[@]}" | \
    rofi -dmenu -i -p "󰌌 Shortcuts" -theme "$HOME/.config/rofi/keybinds.rasi" >/dev/null || true
