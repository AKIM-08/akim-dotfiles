#!/bin/bash

set -euo pipefail

if pgrep -x wlogout >/dev/null; then
    pkill -x wlogout
    exit 0
fi

exec wlogout --protocol layer-shell --buttons-per-row 2 --margin-left 42% --margin-right 42% --margin-top 38% --margin-bottom 38%
