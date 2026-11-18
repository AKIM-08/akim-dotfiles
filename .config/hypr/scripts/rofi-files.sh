#!/usr/bin/env bash
# rofi-files.sh - Files mode of the launcher (Super + Q), as a Rofi script mode.
#
#   Enter        go into a folder / open a file
#   Ctrl+Enter   open the selected folder in the file manager (kb-custom-1)
#   ..           go up one level; typing a path and pressing Enter jumps there
#
# Rofi calls this script again after every action: ROFI_RETV says what happened,
# ROFI_INFO is the selected entry's full path, ROFI_DATA is the current folder.

open_with() {
    setsid -f xdg-open "$1" >/dev/null 2>&1
}

icon_for() {
    case "${1,,}" in
        *.png|*.jpg|*.jpeg|*.webp|*.gif|*.svg|*.bmp) echo image-x-generic ;;
        *.mp4|*.mkv|*.webm|*.avi|*.mov)              echo video-x-generic ;;
        *.mp3|*.flac|*.ogg|*.wav|*.m4a|*.opus)       echo audio-x-generic ;;
        *.pdf)                                       echo application-pdf ;;
        *.zip|*.tar|*.gz|*.xz|*.zst|*.7z|*.rar|*.deb) echo package-x-generic ;;
        *.sh|*.py|*.js|*.ts|*.c|*.h|*.rs|*.go|*.lua) echo text-x-script ;;
        *)                                           echo text-x-generic ;;
    esac
}

list() {
    local dir="$1" name
    printf '\0data\x1f%s\n' "$dir"
    printf '\0use-hot-keys\x1ftrue\n'          # let Ctrl+Enter reach this script
    if [ "$dir" != "/" ]; then
        printf '..\0icon\x1fgo-up\x1finfo\x1f%s\n' "$(dirname "$dir")"
    fi
    # Folders first, then files; hidden entries skipped
    while IFS= read -r name; do
        printf '%s/\0icon\x1ffolder\x1finfo\x1f%s\n' "$name" "${dir%/}/$name"
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -not -name '.*' -type d -printf '%f\n' 2>/dev/null | sort -f)
    while IFS= read -r name; do
        printf '%s\0icon\x1f%s\x1finfo\x1f%s\n' "$name" "$(icon_for "$name")" "${dir%/}/$name"
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -not -name '.*' -not -type d -printf '%f\n' 2>/dev/null | sort -f)
}

cwd="${ROFI_DATA:-$HOME}"

case "${ROFI_RETV:-0}" in
    0)  # first call
        list "$HOME"
        ;;
    1)  # Enter on an entry
        path="${ROFI_INFO:-$cwd}"
        if [ -d "$path" ]; then list "$path"; else open_with "$path"; fi
        ;;
    2)  # Enter on typed text: treat it as a path (absolute, ~/..., or relative)
        p="${1/#\~/$HOME}"
        [[ "$p" != /* ]] && p="${cwd%/}/$p"
        if [ -d "$p" ]; then list "$(realpath "$p")"
        elif [ -f "$p" ]; then open_with "$p"
        else list "$cwd"; fi
        ;;
    10) # Ctrl+Enter: open the folder itself (or the file) instead of entering it
        path="${ROFI_INFO:-$cwd}"
        open_with "$path"
        ;;
    *)
        list "$cwd"
        ;;
esac
