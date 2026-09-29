#!/usr/bin/env bash
# sync-app-icons.sh - Comprehensive web app (Brave, Chrome, Chromium, Flatpak, PWA) icon resolver for Rofi

ICON_DIR="$HOME/.local/share/icons"
HICOLOR_DIR="$ICON_DIR/hicolor"

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

# 2. Extract icons from browser manifest stores (Brave, Chrome, Chromium, Edge, Flatpaks)
find_browser_manifest_icons() {
    local app_id="$1"
    local app_name="$2"
    local search_paths=(
        "$HOME/.config/BraveSoftware"
        "$HOME/.var/app/com.brave.Browser"
        "$HOME/.config/google-chrome"
        "$HOME/.var/app/com.google.Chrome"
        "$HOME/.config/chromium"
        "$HOME/.var/app/org.chromium.Chromium"
        "$HOME/.config/microsoft-edge"
        "$HOME/.local/share/icons"
    )
    for sp in "${search_paths[@]}"; do
        [ -d "$sp" ] || continue
        local found
        if [ -n "$app_id" ]; then
            found=$(find "$sp" -type f \( -name "*${app_id}*.png" -o -path "*/${app_id}/*.png" \) 2>/dev/null | head -1)
            if [ -n "$found" ] && [ -f "$found" ]; then
                echo "$found"
                return 0
            fi
        fi
        if [ -n "$app_name" ]; then
            found=$(find "$sp" -type f -iname "*${app_name}*.png" 2>/dev/null | head -1)
            if [ -n "$found" ] && [ -f "$found" ]; then
                echo "$found"
                return 0
            fi
        fi
    done
    return 1
}

# 3. Application directories to search
APP_DIRS=(
    "$HOME/.local/share/applications"
    "$HOME/.var/app/com.brave.Browser/data/applications"
    "$HOME/.var/app/com.google.Chrome/data/applications"
    "$HOME/.local/share/flatpak/exports/share/applications"
    "$HOME/Desktop"
)

for apps_dir in "${APP_DIRS[@]}"; do
    [ -d "$apps_dir" ] || continue
    
    for desktop in "$apps_dir"/*.desktop; do
        [ -f "$desktop" ] || continue
        
        # Get current Icon line and Name
        icon_val=$(grep -E '^Icon=' "$desktop" | head -1 | cut -d= -f2-)
        app_title=$(grep -E '^Name=' "$desktop" | head -1 | cut -d= -f2-)
        
        # Extract App ID from filename, Exec, or StartupWMClass
        app_id=""
        desktop_base=$(basename "$desktop")
        if [[ "$desktop_base" =~ (brave|chrome|chromium|msedge)-([a-zA-Z0-9_-]+) ]]; then
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

        # Check if current icon_val is already a valid absolute path
        if [[ "$icon_val" == /* ]] && [ -f "$icon_val" ]; then
            target_icon_path="$icon_val"
        fi

        # Search in hicolor directories for matching icon name
        if [ -z "$target_icon_path" ] && [ -n "$icon_val" ]; then
            base_name="${icon_val%.png}"
            base_name="$(basename "$base_name")"
            
            for s in 512x512 256x256 128x128 64x64 48x48 32x32 16x16; do
                if [ -f "$HICOLOR_DIR/$s/apps/${base_name}.png" ]; then
                    target_icon_path="$HICOLOR_DIR/$s/apps/${base_name}.png"
                    break
                elif [ -f "$HICOLOR_DIR/$s/apps/${base_name}" ]; then
                    target_icon_path="$HICOLOR_DIR/$s/apps/${base_name}"
                    break
                fi
            done
            
            if [ -z "$target_icon_path" ]; then
                target_icon_path=$(find "$HICOLOR_DIR" "$ICON_DIR" "$HOME/.var" -maxdepth 5 -type f \( -name "${base_name}.png" -o -name "${base_name}" \) 2>/dev/null | head -1)
            fi
        fi

        # Search browser stores by app_id or app_title
        if [ -z "$target_icon_path" ]; then
            manifest_icon=$(find_browser_manifest_icons "$app_id" "$app_title")
            if [ -n "$manifest_icon" ] && [ -f "$manifest_icon" ]; then
                dest_name="${app_id:-$app_title}"
                dest_icon="$HICOLOR_DIR/128x128/apps/brave-${dest_name}.png"
                cp "$manifest_icon" "$dest_icon" 2>/dev/null || true
                target_icon_path="$dest_icon"
            fi
        fi

        # If found, rewrite .desktop to point to the ABSOLUTE icon path
        if [ -n "$target_icon_path" ] && [ -f "$target_icon_path" ]; then
            if grep -q '^Icon=' "$desktop"; then
                sed -i "s|^Icon=.*|Icon=$target_icon_path|" "$desktop"
            else
                echo "Icon=$target_icon_path" >> "$desktop"
            fi
            
            # Symlink for direct lookup
            base_icon_filename="$(basename "$target_icon_path")"
            ln -sf "$target_icon_path" "$ICON_DIR/$base_icon_filename" 2>/dev/null || true
            [ -n "$app_id" ] && ln -sf "$target_icon_path" "$ICON_DIR/brave-${app_id}-Default.png" 2>/dev/null || true
            [ -n "$app_id" ] && ln -sf "$target_icon_path" "$ICON_DIR/chrome-${app_id}-Default.png" 2>/dev/null || true
            [ -n "$app_title" ] && ln -sf "$target_icon_path" "$ICON_DIR/${app_title}.png" 2>/dev/null || true
        fi
    done
done

# 4. Refresh icon caches and desktop databases
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
    gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true
fi

for apps_dir in "${APP_DIRS[@]}"; do
    if [ -d "$apps_dir" ] && command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
    fi
done
