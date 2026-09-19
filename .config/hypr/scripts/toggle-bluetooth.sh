#!/bin/bash
# toggle-bluetooth.sh - Toggle bluetooth power state
if bluetoothctl show 2>/dev/null | grep -q "Powered: yes"; then
    bluetoothctl power off
else
    rfkill unblock bluetooth 2>/dev/null || true
    bluetoothctl power on
fi
