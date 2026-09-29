#!/usr/bin/env bash
# check-updates.sh - Debian update counter for Waybar

count=0

if command -v apt-get &>/dev/null; then
    deb_count=$(apt-get -s upgrade 2>/dev/null | grep -E '^[0-9]+ upgraded' | awk '{print $1}')
    if [ -n "$deb_count" ]; then
        count=$deb_count
    fi
fi

echo "${count:-0}"
