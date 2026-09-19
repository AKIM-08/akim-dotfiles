#!/bin/bash
# bluetooth-toggle.sh - Ensure bluetooth is unblocked/powered and launch manager

# 1. Unblock bluetooth at kernel/rfkill level
rfkill unblock bluetooth 2>/dev/null || true

# 2. Power on bluetooth controller
bluetoothctl power on 2>/dev/null || true

# 3. Launch the preferred Bluetooth management interface
if command -v blueman-manager &>/dev/null; then
    blueman-manager &
elif command -v overskride &>/dev/null; then
    overskride &
else
    kitty -e bluetoothctl &
fi
