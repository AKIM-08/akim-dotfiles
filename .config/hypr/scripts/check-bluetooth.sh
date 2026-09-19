#!/bin/bash
# check-bluetooth.sh - Returns true if bluetooth adapter is powered on
if bluetoothctl show 2>/dev/null | grep -q "Powered: yes"; then
    echo "true"
else
    echo "false"
fi
