#!/bin/bash

set -euo pipefail

hyprctl dispatch togglefloating >/dev/null
hyprctl dispatch centerwindow >/dev/null
