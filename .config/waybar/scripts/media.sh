#!/usr/bin/env bash
# media.sh - Now-playing for Waybar's custom/media module.
# Prints one JSON line per change. The text is empty (Waybar hides the module) unless a player
# is playing or paused with a real title; browsers and players that sit idle with no title
# would otherwise leave an empty chip on the bar.

TITLE_MAX=24

json_escape() {
    local s="${1//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/ }"
    printf '%s' "$s"
}

emit_empty() { echo '{"text": "", "class": "stopped"}'; }

playerctl --follow metadata --format $'{{status}}\t{{title}}\t{{artist}}' 2>/dev/null |
while IFS=$'\t' read -r status title artist; do
    case "$status" in
        Playing) alt="playing" ;;
        Paused)  alt="paused" ;;
        *)       emit_empty; continue ;;
    esac
    if [ -z "${title// /}" ]; then
        emit_empty
        continue
    fi

    short="$title"
    [ "${#short}" -gt "$TITLE_MAX" ] && short="${short:0:$((TITLE_MAX - 1))}…"
    tip="$title"
    [ -n "$artist" ] && tip="$artist - $title"

    printf '{"text": "%s", "alt": "%s", "class": "%s", "tooltip": "%s\\nClick: play/pause  Right-click: next  Middle-click: previous"}\n' \
        "$(json_escape "$short")" "$alt" "$alt" "$(json_escape "$tip")"
done

# playerctl exited (no D-Bus session, etc.): hide the module; Waybar restarts the script
emit_empty
