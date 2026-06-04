#!/bin/bash

set -euo pipefail

if pgrep -x wlogout >/dev/null; then
    pkill -x wlogout
    exit 0
fi

exec wlogout --protocol layer-shell --buttons-per-row 2 --margin-left 35% --margin-right 35% --margin-top 32% --margin-bottom 32%
