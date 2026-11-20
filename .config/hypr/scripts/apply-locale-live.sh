#!/usr/bin/env bash
# apply-locale-live.sh <locale>   e.g. fr_FR.UTF-8 - use a new language without logging out.
#
# Run by Settings -> Language & region after set-locale.sh changed the system language.
# Each program copies the language when it starts, so: give the new one to Hyprland (apps
# opened from now on get it) and to the services that start apps in the background, then
# restart the bar and notifications. Apps already open keep the old language until reopened;
# the login and lock screens switch at the next login.

loc="$1"
case "$loc" in
    ""|*[!A-Za-z0-9_.@-]*) echo "usage: apply-locale-live.sh <locale, e.g. fr_FR.UTF-8>" >&2; exit 2 ;;
esac
lang="${loc%%.*}"                       # fr_FR
language="$lang:${lang%%_*}"            # fr_FR:fr  (same as set-locale.sh writes)

export LANG="$loc" LANGUAGE="$language"
unset LC_ALL

# Hyprland: everything it starts from now on (shortcuts, launcher, exec)
hyprctl --batch "keyword env LANG,$loc ; keyword env LANGUAGE,$language" >/dev/null 2>&1

# systemd user services and D-Bus-activated apps (portals, file manager...)
systemctl --user set-environment LANG="$loc" LANGUAGE="$language" 2>/dev/null
command -v dbus-update-activation-environment >/dev/null \
    && dbus-update-activation-environment --systemd LANG LANGUAGE 2>/dev/null

# Bar (or island / dock) and notifications, restarted with the new language
setsid -f "$HOME/.config/waybar/scripts/launch.sh" >/dev/null 2>&1
if pgrep -x swaync >/dev/null; then
    pkill -x swaync
    for _ in 1 2 3 4 5 6 7 8 9 10; do pgrep -x swaync >/dev/null || break; sleep 0.1; done
    setsid -f "$HOME/.config/swaync/start.sh" >/dev/null 2>&1
fi
exit 0
