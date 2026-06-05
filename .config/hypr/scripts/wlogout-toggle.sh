#!/bin/bash

set -euo pipefail

if pgrep -x wlogout >/dev/null; then
    pkill -x wlogout
    exit 0
fi

exec wlogout --protocol layer-shell
