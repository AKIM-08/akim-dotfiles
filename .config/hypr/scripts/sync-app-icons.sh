#!/usr/bin/env bash
# sync-app-icons.sh - Ensure web apps (Brave, Chrome, PWA) and local icons are recognized by Rofi / GTK

ICON_DIR="$HOME/.local/share/icons"
HICOLOR_DIR="$ICON_DIR/hicolor"
APPS_DIR="$HOME/.local/share/applications"

mkdir -p "$HICOLOR_DIR"
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    mkdir -p "$HICOLOR_DIR/$size/apps"
done

# 1. Ensure hicolor index.theme exists in user icon directory
if [ ! -f "$HICOLOR_DIR/index.theme" ]; then
    if [ -f "/usr/share/icons/hicolor/index.theme" ]; then
        cp "/usr/share/icons/hicolor/index.theme" "$HICOLOR_DIR/index.theme"
    else
        cat << 'EOF' > "$HICOLOR_DIR/index.theme"
[Icon Theme]
Name=Hicolor
Comment=Fallback icon theme
Hidden=true
Directories=16x16/apps,24x24/apps,32x32/apps,48x48/apps,64x64/apps,128x128/apps,256x256/apps,512x512/apps

[16x16/apps]
Size=16
Type=Threshold

[24x24/apps]
Size=24
Type=Threshold

[32x32/apps]
Size=32
Type=Threshold

[48x48/apps]
Size=48
Type=Threshold

[64x64/apps]
Size=64
Type=Threshold

[128x128/apps]
Size=128
Type=Threshold

[256x256/apps]
Size=256
Type=Threshold

[512x512/apps]
Size=512
Type=Threshold
EOF
    fi
fi

# 2. Fix web app desktop files and icon paths (Brave / Chrome / Chromium / Edge PWAs)
if [ -d "$APPS_DIR" ]; then
    shopt -s nullglob
    for desktop in "$APPS_DIR"/brave-*.desktop "$APPS_DIR"/chrome-*.desktop "$APPS_DIR"/msedge-*.desktop; do
        [ -f "$desktop" ] || continue
        
        # Extract Icon value
        icon_name=$(grep -E '^Icon=' "$desktop" | head -1 | cut -d= -f2-)
        [ -z "$icon_name" ] && continue
        
        # If Icon is an absolute path that doesn't exist, try resolving it in hicolor
        if [[ "$icon_name" == /* ]] && [ ! -f "$icon_name" ]; then
            base_icon=$(basename "$icon_name")
            found_icon=$(find "$HICOLOR_DIR" -name "$base_icon" 2>/dev/null | head -1)
            if [ -n "$found_icon" ]; then
                sed -i "s|^Icon=.*|Icon=$found_icon|" "$desktop"
            fi
        fi
        
        # If Icon is a name (e.g. brave-app-id-Default), verify it exists in hicolor; if found in one size, link to all
        if [[ "$icon_name" != /* ]]; then
            icon_file=$(find "$HICOLOR_DIR" -name "${icon_name}.png" -o -name "${icon_name}" 2>/dev/null | head -1)
            if [ -n "$icon_file" ]; then
                # Link to top-level icon dir as well for maximum compatibility
                [ -f "$icon_file" ] && ln -sf "$icon_file" "$ICON_DIR/${icon_name}.png" 2>/dev/null || true
                [ -f "$icon_file" ] && ln -sf "$icon_file" "$ICON_DIR/${icon_name}" 2>/dev/null || true
            fi
        fi
    done
    shopt -u nullglob
fi

# 3. Update icon caches and desktop database
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
    [ -d "$ICON_DIR" ] && gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true
fi

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
