#!/usr/bin/env bash
# cc-sync.sh - Keep the SwayNC control-center tiles in sync while the panel is open.
#
# SwayNC only asks a toggle tile for its state when the panel opens, so muting with a key
# while it is open left the Mute tile showing the old state. This runs in the background
# (exec-once): while the panel is visible it checks the toggles once a second and, if one
# changed from outside the panel, reopens the panel so SwayNC re-reads every tile.
# Changes made by clicking a tile are already shown correctly (see cc-action.sh).
# When the panel is closed it only reads a small state file once a second.

RUN="${XDG_RUNTIME_DIR:-/tmp}"
VISIBLE="$RUN/cc-visible"
OWN="$RUN/cc-own-action"
S="$HOME/.config/hypr/scripts"

exec 9>"$RUN/cc-sync.lock"
flock -n 9 || exit 0                     # already running

snapshot() {
    printf '%s %s %s %s %s %s' \
        "$("$S/check-mute.sh")" "$("$S/check-mic.sh")" "$("$S/check-bluetooth.sh")" \
        "$(swaync-client -D 2>/dev/null)" "$("$S/nightlight.sh" is-on)" \
        "$([ -f "$HOME/.cache/caffeine_active" ] && echo true || echo false)"
}

# Follow the panel's visibility from SwayNC's event stream (restarted if SwayNC restarts)
echo 0 > "$VISIBLE"
(
    exec 9>&-
    while true; do
        swaync-client -s 2>/dev/null | while IFS= read -r line; do
            case "$line" in
                *'"visible": true'*|*'"visible":true'*) echo 1 > "$VISIBLE" ;;
                *'"visible"'*)                           echo 0 > "$VISIBLE" ;;
            esac
        done
        echo 0 > "$VISIBLE"
        sleep 2
    done
) &

was=0
base=""
while sleep 1; do
    vis=$(cat "$VISIBLE" 2>/dev/null || echo 0)
    if [ "$vis" = 1 ]; then
        cur=$(snapshot)
        if [ "$was" != 1 ]; then
            base="$cur"                  # just opened: SwayNC read every tile itself
        elif [ "$cur" != "$base" ]; then
            own=$(stat -c %Y "$OWN" 2>/dev/null || echo 0)
            if [ $(( $(date +%s) - own )) -gt 2 ]; then
                # Changed outside the panel (keyboard, another menu): reopen to refresh tiles
                swaync-client -cp >/dev/null 2>&1
                sleep 0.25
                swaync-client -op >/dev/null 2>&1
            fi
            base="$cur"
        fi
    fi
    was="$vis"
done
