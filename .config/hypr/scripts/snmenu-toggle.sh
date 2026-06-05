#!/bin/bash

set -euo pipefail

if pgrep -x snmenu >/dev/null; then
    pkill -x snmenu
    exit 0
fi

exec snmenu -l "$HOME/.config/snmenu/layout" -C "$HOME/.config/snmenu/style.css"
