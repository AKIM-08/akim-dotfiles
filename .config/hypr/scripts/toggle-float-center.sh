#!/bin/bash
# toggle-float-center.sh — Met la fenêtre en flottant centré, ou la remet en tiled

set -euo pipefail

hyprctl dispatch togglefloating >/dev/null

# Centrer uniquement si la fenêtre est maintenant en floating
floating=$(hyprctl activewindow -j 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('floating', False))" 2>/dev/null || echo "False")
if [ "$floating" = "True" ]; then
    hyprctl dispatch centerwindow >/dev/null
fi
