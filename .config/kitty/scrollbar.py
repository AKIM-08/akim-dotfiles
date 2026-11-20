# Read by kitty.conf (geninclude): prints the scrollbar settings when this kitty has a scrollbar
# (0.43+), and nothing on older versions, which would complain about unknown options.
# Debian 13 ships kitty 0.41: install/kitty-latest.sh installs the official newer build.
import re
import subprocess

try:
    from kitty.constants import version as v          # kitty runs this with its own Python
    version = tuple(v)[:3]
except Exception:
    try:
        out = subprocess.run(["kitty", "--version"], capture_output=True, text=True, timeout=3).stdout
        version = tuple(int(x) for x in re.search(r"(\d+)\.(\d+)\.(\d+)", out).groups())
    except Exception:
        version = (0, 0, 0)

if version >= (0, 43, 0):
    print("""
# A scrollbar you can grab: appears while scrolled or hovered, wider under the mouse,
# click the track to jump there
scrollbar                    scrolled-or-hovered
scrollbar_interactive        yes
scrollbar_jump_on_click      yes
scrollbar_width              0.6
scrollbar_hover_width        1.2
scrollbar_hitbox_expansion   1
scrollbar_min_handle_height  2
scrollbar_handle_opacity     0.8
scrollbar_radius             0.5
scrollbar_track_opacity      0
scrollbar_track_hover_opacity 0.15
scrollbar_handle_color       selection_background
""")
