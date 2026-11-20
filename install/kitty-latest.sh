#!/usr/bin/env bash
# kitty-latest.sh (kitty-update) - kitty's official build, newer than Debian's.
#
# Debian 13 ships kitty 0.41; the grabbable scrollbar needs 0.43+. This installs kitty's own
# build into ~/.local/kitty.app (the method its authors recommend) and links it from
# /usr/local/bin, which comes before /usr/bin, so every launcher, shortcut and script uses it.
# Your kitty.conf and colors stay the same.
#
#   kitty-latest.sh            install if the current kitty is older than 0.43 (the installer)
#   kitty-update               update to the newest kitty if there is one (same as --update)
#   kitty-latest.sh --update   same
#   kitty-latest.sh --quiet    with --update: say nothing when already up to date (akim-update)
#   kitty-latest.sh --remove   go back to Debian's kitty

set -euo pipefail
APP="$HOME/.local/kitty.app"
SELF=$(readlink -f "${BASH_SOURCE[0]}")

version_of() { "$1" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1; }
newer_or_equal() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

mode=install quiet=false
[ "$(basename "$0")" = kitty-update ] && mode=update
for a in "$@"; do
    case "$a" in
        --update) mode=update ;;
        --remove) mode=remove ;;
        --quiet)  quiet=true ;;
    esac
done
say() { $quiet || echo "$@"; }

# The short command for everyone: kitty-update
mkdir -p "$HOME/.local/bin"
[ "$(readlink -f "$HOME/.local/bin/kitty-update" 2>/dev/null)" = "$SELF" ] || ln -sf "$SELF" "$HOME/.local/bin/kitty-update"

if [ "$mode" = remove ]; then
    sudo rm -f /usr/local/bin/kitty /usr/local/bin/kitten
    sudo update-alternatives --set x-terminal-emulator /usr/bin/kitty 2>/dev/null || true
    rm -rf "$APP"
    echo "Back to Debian's kitty $(version_of /usr/bin/kitty). Open a new kitty window."
    exit 0
fi

current=$(version_of kitty || true)
if [ "$mode" = install ]; then
    if [ -n "$current" ] && newer_or_equal "$current" 0.43.0; then
        say "kitty $current already has the scrollbar."
        exit 0
    fi
else
    if [ ! -x "$APP/bin/kitty" ]; then
        say "kitty comes from Debian here (updated by apt). For the newer one: bash $SELF"
        exit 0
    fi
    latest=$(curl -fsSL --max-time 10 https://sw.kovidgoyal.net/kitty/current-version.txt 2>/dev/null | tr -d '[:space:]')
    if [ -z "$latest" ]; then
        say "Couldn't check for a new kitty (no internet?)."
        exit 0
    fi
    installed=$(version_of "$APP/bin/kitty")
    if [ -n "$installed" ] && newer_or_equal "$installed" "$latest"; then
        say "kitty $installed is up to date."
        exit 0
    fi
    current="$installed"
    quiet=false
fi

echo "--> Installing kitty ${latest:-(newest)} (now: ${current:-none})..."
curl -fsSL https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin launch=n >/dev/null \
    || { echo "kitty download failed (no internet?)"; exit 1; }
[ -x "$APP/bin/kitty" ] || { echo "kitty install failed"; exit 1; }

# Links only need setting once (an update replaces what they point to): no password then
for b in kitty kitten; do
    [ "$(readlink "/usr/local/bin/$b" 2>/dev/null)" = "$APP/bin/$b" ] || sudo ln -sf "$APP/bin/$b" "/usr/local/bin/$b"
done
if command -v update-alternatives >/dev/null && [ "$(readlink -f /etc/alternatives/x-terminal-emulator 2>/dev/null)" != "$(readlink -f "$APP/bin/kitty")" ]; then
    sudo update-alternatives --install /usr/bin/x-terminal-emulator x-terminal-emulator /usr/local/bin/kitty 60 >/dev/null 2>&1 || true
    sudo update-alternatives --set x-terminal-emulator /usr/local/bin/kitty >/dev/null 2>&1 || true
fi
echo "--> kitty $(version_of "$APP/bin/kitty") installed. Close kitty and open it again to use it."
