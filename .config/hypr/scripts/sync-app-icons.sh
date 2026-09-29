#!/usr/bin/env bash
# sync-app-icons.sh - Robust web app (Brave, Chrome, Chromium, PWA) icon resolver for Rofi & desktop

ICON_DIR="$HOME/.local/share/icons"
HICOLOR_DIR="$ICON_DIR/hicolor"
APPS_DIR="$HOME/.local/share/applications"

mkdir -p "$ICON_DIR" "$HICOLOR_DIR"
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    mkdir -p "$HICOLOR_DIR/$size/apps"
done

# 1. Ensure hicolor index.theme exists
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

# 2. Extract icons from browser manifest stores (Brave, Chrome, Chromium, Edge) if missing
find_browser_manifest_icons() {
    local app_id="$1"
    local search_paths=(
        "$HOME/.config/BraveSoftware"
        "$HOME/.config/google-chrome"
        "$HOME/.config/chromium"
        "$HOME/.config/microsoft-edge"
    )
    for sp in "${search_paths[@]}"; do
        [ -d "$sp" ] || continue
        local found
        # Look for largest png matching this app id in Manifest Resources
        found=$(find "$sp" -type f -name "*${app_id}*.png" -o -path "*/${app_id}/*.png" 2>/dev/null | head -1)
        if [ -n "$found" ] && [ -f "$found" ]; then
            echo "$found"
            return 0
        fi
    done
    return 1
}

# 3. Process every desktop file in user applications directory
if [ -d "$APPS_DIR" ]; then
    shopt -s nullglob
    for desktop in "$APPS_DIR"/*.desktop; do
        [ -f "$desktop" ] || continue
        
        # Get current Icon line
        icon_val=$(grep -E '^Icon=' "$desktop" | head -1 | cut -d= -f2-)
        [ -z "$icon_val" ] && continue
        
        # Extract App ID from filename, Exec, or StartupWMClass
        app_id=""
        if [[ "$desktop" =~ (brave|chrome|chromium|msedge)-([a-zA-Z0-9_-]+)-Default\.desktop ]]; then
            app_id="${BASH_REMATCH[2]}"
        fi
        if [ -z "$app_id" ]; then
            exec_line=$(grep -E '^Exec=' "$desktop" | head -1)
            if [[ "$exec_line" =~ --app-id=([a-zA-Z0-9_-]+) ]]; then
                app_id="${BASH_REMATCH[1]}"
            fi
        fi
        if [ -z "$app_id" ]; then
            wm_line=$(grep -E '^StartupWMClass=' "$desktop" | head -1)
            if [[ "$wm_line" =~ crx_([a-zA-Z0-9_-]+) ]]; then
                app_id="${BASH_REMATCH[1]}"
            fi
        fi

        target_icon_path=""

        # If icon_val is already an existing absolute path to an image file, keep it
        if [[ "$icon_val" == /* ]] && [ -f "$icon_val" ]; then
            target_icon_path="$icon_val"
        fi

        # Search in hicolor directories for matching icon name
        if [ -z "$target_icon_path" ]; then
            base_name="${icon_val%.png}"
            base_name="$(basename "$base_name")"
            
            # Prefer higher resolution: 512, 256, 128, 64, 48, 32, 16
            for s in 512x512 256x256 128x128 64x64 48x48 32x32 16x16; do
                if [ -f "$HICOLOR_DIR/$s/apps/${base_name}.png" ]; then
                    target_icon_path="$HICOLOR_DIR/$s/apps/${base_name}.png"
                    break
                elif [ -f "$HICOLOR_DIR/$s/apps/${base_name}" ]; then
                    target_icon_path="$HICOLOR_DIR/$s/apps/${base_name}"
                    break
                fi
            done
            
            # Generic find in user icons
            if [ -z "$target_icon_path" ]; then
                target_icon_path=$(find "$HICOLOR_DIR" "$ICON_DIR" -maxdepth 4 -type f \( -name "${base_name}.png" -o -name "${base_name}" \) 2>/dev/null | head -1)
            fi
        fi

        # If not found and we have an app_id, search browser cache/manifest
        if [ -z "$target_icon_path" ] && [ -n "$app_id" ]; then
            manifest_icon=$(find_browser_manifest_icons "$app_id")
            if [ -n "$manifest_icon" ] && [ -f "$manifest_icon" ]; then
                dest_icon="$HICOLOR_DIR/128x128/apps/brave-${app_id}-Default.png"
                cp "$manifest_icon" "$dest_icon" 2>/dev/null || true
                target_icon_path="$dest_icon"
            fi
        fi

        # If found, ensure .desktop file explicitly uses the ABSOLUTE PATH so Rofi loads it directly
        if [ -n "$target_icon_path" ] && [ -f "$target_icon_path" ]; then
            sed -i "s|^Icon=.*|Icon=$target_icon_path|" "$desktop"
            # Also create top-level symlink in ~/.local/share/icons/
            base_icon_filename="$(basename "$target_icon_path")"
            ln -sf "$target_icon_path" "$ICON_DIR/$base_icon_filename" 2>/dev/null || true
            [ -n "$app_id" ] && ln -sf "$target_icon_path" "$ICON_DIR/brave-${app_id}-Default.png" 2>/dev/null || true
            [ -n "$app_id" ] && ln -sf "$target_icon_path" "$ICON_DIR/chrome-${app_id}-Default.png" 2>/dev/null || true
        fi
    done
    shopt -u nullglob
fi

# 4. Refresh icon caches and desktop database
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
    gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true
fi

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
