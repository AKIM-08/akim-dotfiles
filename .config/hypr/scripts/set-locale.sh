#!/bin/sh
# set-locale.sh <locale>   e.g. fr_FR.UTF-8 - make it the system language (Debian)
#
# Run as root through pkexec by Settings -> Language & region:
#   pkexec /bin/sh ~/.config/hypr/scripts/set-locale.sh fr_FR.UTF-8
# Enables the locale in /etc/locale.gen, generates it and makes it the default for every new
# login (/etc/default/locale). Settings then runs apply-locale-live.sh for the running session.

set -e

loc="$1"
case "$loc" in
    ""|*[!A-Za-z0-9_.@-]*) echo "usage: set-locale.sh <locale, e.g. fr_FR.UTF-8>" >&2; exit 2 ;;
esac
[ "$(id -u)" -eq 0 ] || { echo "set-locale.sh must run as root (pkexec)" >&2; exit 1; }

charset="${loc#*.}"
[ "$charset" = "$loc" ] && charset="UTF-8"

# Enable the line "fr_FR.UTF-8 UTF-8" (commented out in Debian's list), or add it
if grep -q "^# *$loc $charset" /etc/locale.gen; then
    sed -i "s/^# *\($loc $charset\)/\1/" /etc/locale.gen
elif ! grep -q "^$loc $charset" /etc/locale.gen; then
    echo "$loc $charset" >> /etc/locale.gen
fi

locale-gen

lang="${loc%%.*}"                       # fr_FR
update-locale LANG="$loc" LANGUAGE="$lang:${lang%%_*}"
echo "System language set to $loc (applies at the next login)"
