#!/bin/bash

set -euo pipefail

if pgrep -x wlogout >/dev/null; then
    pkill -x wlogout
    exit 0
fi

# Marges pour centrer la grille 2x2 et obtenir la taille de l'image 2
exec wlogout --protocol layer-shell --buttons-per-row 2 --margin-left 25% --margin-right 25% --margin-top 25% --margin-bottom 25%
