#!/usr/bin/env bash
# scratchpad-toggle.sh — Basculer la fenêtre active dans / hors du scratchpad (special:magic)

set -euo pipefail

python3 -c "
import subprocess, json, sys

try:
    win_raw = subprocess.check_output(['hyprctl', 'activewindow', '-j'], text=True).strip()
    if not win_raw:
        sys.exit(0)
    win = json.loads(win_raw)
    if not win or 'workspace' not in win:
        sys.exit(0)

    ws_name = str(win.get('workspace', {}).get('name', ''))
    
    if ws_name.startswith('special'):
        # La fenêtre est déjà dans le scratchpad -> on la ramène sur le workspace normal actif
        mon_raw = subprocess.check_output(['hyprctl', 'monitors', '-j'], text=True)
        monitors = json.loads(mon_raw)
        target_ws = '1'
        for m in monitors:
            if m.get('focused', False):
                target_ws = str(m.get('activeWorkspace', {}).get('id', 1))
                break
        else:
            if monitors:
                target_ws = str(monitors[0].get('activeWorkspace', {}).get('id', 1))
        
        subprocess.run(['hyprctl', 'dispatch', 'movetoworkspace', target_ws], stdout=subprocess.DEVNULL)
    else:
        # La fenêtre est sur un workspace normal -> on l'envoie dans le scratchpad
        subprocess.run(['hyprctl', 'dispatch', 'movetoworkspace', 'special:magic'], stdout=subprocess.DEVNULL)
except Exception:
    sys.exit(0)
"
