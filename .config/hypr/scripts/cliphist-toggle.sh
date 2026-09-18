#!/bin/bash
# Toggle clipboard history picker (Rofi + cliphist with thumbnail previews)

MARKER="${XDG_RUNTIME_DIR:-/tmp}/akim-cliphist-rofi"

if [ -f "$MARKER" ] && pgrep -x rofi >/dev/null; then
    pkill -x rofi
    rm -f "$MARKER"
    exit 0
fi

touch "$MARKER"
trap 'rm -f "$MARKER"' EXIT

CACHE_DIR="${XDG_RUNTIME_DIR:-/tmp}/cliphist-thumbs"
mkdir -p "$CACHE_DIR"

gen_list() {
    cliphist list | head -n 100 | while IFS=$'\t' read -r id content; do
        if [[ "$content" =~ ^\[\[\ binary\ data ]]; then
            thumb="$CACHE_DIR/${id}.png"
            if [ ! -s "$thumb" ]; then
                printf "%s\t%s\n" "$id" "$content" | cliphist decode > "$thumb" 2>/dev/null
            fi
            if [ -s "$thumb" ]; then
                printf "%s\t%s\0icon\x1f%s\n" "$id" "$content" "$thumb"
                continue
            fi
        fi
        printf "%s\t%s\0icon\x1fedit-paste\n" "$id" "$content"
    done
}

sel=$(gen_list | rofi -dmenu -i -p "󰅍 Clipboard" -config "$HOME/.config/rofi/clipboard.rasi")
[ -n "$sel" ] && printf '%s\n' "$sel" | cliphist decode | wl-copy
