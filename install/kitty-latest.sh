#!/usr/bin/env bash
# kitty-latest.sh - install the official kitty build when Debian's is too old for the scrollbar.
#
# Debian 13 ships kitty 0.41; the grabbable scrollbar needs 0.43+. This installs kitty's own
# build into ~/.local/kitty.app (the method its authors recommend) and links it from
# /usr/local/bin, which comes before /usr/bin, so every launcher, shortcut and script uses it.
# Your kitty.conf and colors stay the same. Run it again later to update kitty.
#
#   kitty-latest.sh           install if the current kitty is older than 0.43
#   kitty-latest.sh --update  install the newest build anyway
#   kitty-latest.sh --remove  go back to Debian's kitty

set -euo pipefail
APP="$HOME/.local/kitty.app"

version_of() { "$1" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1; }
newer_or_equal() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

if [ "${1:-}" = "--remove" ]; then
    sudo rm -f /usr/local/bin/kitty /usr/local/bin/kitten
    sudo update-alternatives --set x-terminal-emulator /usr/bin/kitty 2>/dev/null || true
    rm -rf "$APP"
    echo "Back to Debian's kitty $(version_of /usr/bin/kitty). Open a new kitty window."
    exit 0
fi

current=$(version_of kitty || true)
if [ "${1:-}" != "--update" ] && [ -n "$current" ] && newer_or_equal "$current" 0.43.0; then
    echo "kitty $current already has the scrollbar."
    exit 0
fi

echo "--> Installing the official kitty build (current: ${current:-none})..."
curl -fsSL https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin launch=n >/dev/null \
    || { echo "kitty download failed (no internet?)"; exit 1; }
[ -x "$APP/bin/kitty" ] || { echo "kitty install failed"; exit 1; }

sudo ln -sf "$APP/bin/kitty" /usr/local/bin/kitty
sudo ln -sf "$APP/bin/kitten" /usr/local/bin/kitten
if command -v update-alternatives >/dev/null; then
    sudo update-alternatives --install /usr/bin/x-terminal-emulator x-terminal-emulator /usr/local/bin/kitty 60 >/dev/null 2>&1 || true
    sudo update-alternatives --set x-terminal-emulator /usr/local/bin/kitty >/dev/null 2>&1 || true
fi
hash -r
echo "--> kitty $(version_of /usr/local/bin/kitty) installed. Close kitty and open it again to use it."
