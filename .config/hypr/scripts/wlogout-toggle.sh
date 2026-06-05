#!/bin/bash
# wlogout-toggle.sh — toggle du menu d'alimentation circular
# L'avatar est injecté dans un CSS temporaire car GTK3 CSS
# n'accepte pas les variables shell ni ~ dans les URL.

set -euo pipefail

if pgrep -x wlogout > /dev/null; then
    pkill -x wlogout
    exit 0
fi

STYLE="$HOME/.config/wlogout/style.css"
AVATAR=""

# Chercher l'avatar dans l'ordre de priorité
for candidate in \
    "$HOME/.face" \
    "$HOME/Pictures/akim-avatar.png" \
    "$HOME/.face.icon"; do
    if [ -f "$candidate" ]; then
        AVATAR="$candidate"
        break
    fi
done

# Générer un CSS temporaire qui importe le style principal
# et injecte l'avatar dans window (GTK3 impose un chemin absolu)
TMP_CSS=$(mktemp /tmp/wlogout-XXXXXX.css)
trap 'rm -f "$TMP_CSS"' EXIT

if [ -n "$AVATAR" ]; then
    cat > "$TMP_CSS" << EOF
@import url("${STYLE}");
window {
  background-image: image(url("${AVATAR}"));
  background-size:     110px 110px;
  background-repeat:   no-repeat;
  background-position: center;
}
EOF
else
    # Pas d'avatar : import seul
    printf '@import url("%s");\n' "$STYLE" > "$TMP_CSS"
fi

exec wlogout --protocol layer-shell --css "$TMP_CSS"
