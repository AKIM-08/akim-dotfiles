#!/usr/bin/env bash
# set-wallpaper.sh <image> [awww transition] - switch the wallpaper, then retheme
#
# Uses the wallfx transition (character outline first / pixel colonies) unless
# ~/.config/hypr/wallpaper-transition says "classic"; the awww transition given here is
# used for classic mode and whenever wallfx can't run.

WALLPAPER_DIR="$HOME/Pictures/wallpapers"
CURRENT="$WALLPAPER_DIR/current.jpg"
WALLFX="$HOME/.config/hypr/scripts/wallfx"
WALLFX_VENV="$HOME/.local/share/wallfx/venv/bin/python"
MODE_FILE="$HOME/.config/hypr/wallpaper-transition"
APPLY_THEME="$HOME/.config/hypr/scripts/apply-pywal-theme.sh"

new=$(readlink -f "$1" 2>/dev/null)
if [ -z "$new" ] || [ ! -f "$new" ]; then
    notify-send -u critical "Wallpaper" "Not found: $1" 2>/dev/null
    exit 1
fi
fallback="${2:-outer}"
old=$(readlink -f "$CURRENT" 2>/dev/null)
ln -sf "$new" "$CURRENT"

if ! pgrep -x awww-daemon >/dev/null; then
    awww-daemon >/dev/null 2>&1 & disown
    sleep 0.5
fi

mode=$(cat "$MODE_FILE" 2>/dev/null || echo outline)
played=""
# Each switch logs what wallfx did, so a silent failure can be diagnosed
LOG="$HOME/.cache/wallfx/last.log"
mkdir -p "$(dirname "$LOG")"
{ echo "== $(date '+%F %T')  mode=$mode"; echo "old: $old"; echo "new: $new"; } > "$LOG"

if [ "$mode" != classic ] && [ -f "$old" ] && [ "$old" != "$new" ]; then
    py=python3; [ -x "$WALLFX_VENV" ] && py="$WALLFX_VENV"
    map=$("$py" "$WALLFX/wallfx-map.py" get "$new" 2>>"$LOG")
    echo "map ($py): ${map:-<none>}" >> "$LOG"
    if [ -n "$map" ] && [ -f "$map" ]; then
        # Falls back to the awww transition by itself if GTK layer shell / OpenGL are missing
        python3 "$WALLFX/wallfx-play.py" "$old" "$new" "$map" --fallback "$fallback" >>"$LOG" 2>&1 &
        played=1
    fi
elif [ "$old" = "$new" ]; then
    echo "same wallpaper as before: nothing to animate" >> "$LOG"
fi

if [ -z "$played" ]; then
    awww img "$new" --transition-type "$fallback" --transition-angle 30 --transition-step 90 \
        --transition-fps 60 --filter Lanczos3 --resize crop
fi

# Recolor while the transition plays
"$APPLY_THEME" "$new"
wait
