#!/usr/bin/env bash
# check-updates.sh - Multi-distro update counter for Waybar

count=0

# Arch Linux (pacman / AUR)
if command -v checkupdates &>/dev/null; then
    arch_count=$(checkupdates 2>/dev/null | wc -l)
    count=$((count + arch_count))
    if command -v yay &>/dev/null; then
        aur_count=$(yay -Qua 2>/dev/null | wc -l)
        count=$((count + aur_count))
    elif command -v paru &>/dev/null; then
        aur_count=$(paru -Qua 2>/dev/null | wc -l)
        count=$((count + aur_count))
    fi
# Debian / Ubuntu (apt / nala)
elif command -v apt-get &>/dev/null; then
    deb_count=$(apt-get -s upgrade 2>/dev/null | grep -E '^[0-9]+ upgraded' | awk '{print $1}')
    if [ -n "$deb_count" ]; then
        count=$deb_count
    else
        count=0
    fi
# Fedora / RHEL (dnf)
elif command -v dnf &>/dev/null; then
    fedora_count=$(dnf check-update -q 2>/dev/null | grep -c '^[a-zA-Z0-9]')
    count=$fedora_count
fi

echo "${count:-0}"
