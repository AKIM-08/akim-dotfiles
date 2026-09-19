#!/usr/bin/env bash
# system-update.sh - Interactive system updater for Waybar

BOLD="\033[1m"
GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
CYAN="\033[1;36m"
RED="\033[1;31m"
RESET="\033[0m"

clear
echo -e "${CYAN}========================================================================${RESET}"
echo -e "${BOLD}                     󰅢  SYSTEM UPDATE & UPGRADE                       ${RESET}"
echo -e "${CYAN}========================================================================${RESET}"
echo ""

# Detect Distribution & Package Manager
if command -v yay &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Detected Arch Linux with yay (Pacman + AUR)...${RESET}"
    echo ""
    yay -Syu
elif command -v paru &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Detected Arch Linux with paru (Pacman + AUR)...${RESET}"
    echo ""
    paru -Syu
elif command -v pacman &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Detected Arch Linux (pacman)...${RESET}"
    echo ""
    sudo pacman -Syu
elif command -v nala &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Detected Debian/Ubuntu with nala...${RESET}"
    echo ""
    sudo nala update && sudo nala upgrade
elif command -v apt-get &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Detected Debian/Ubuntu (APT)...${RESET}"
    echo ""
    echo -e "${YELLOW}--> Updating package lists...${RESET}"
    sudo apt update
    echo ""
    echo -e "${YELLOW}--> Upgrading packages...${RESET}"
    sudo apt upgrade
    echo ""
    echo -e "${YELLOW}--> Cleaning unused dependencies...${RESET}"
    sudo apt autoremove -y
elif command -v dnf &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Detected Fedora (DNF)...${RESET}"
    echo ""
    sudo dnf upgrade
else
    echo -e "${RED}Error: No supported package manager found (apt, nala, yay, paru, pacman, dnf).${RESET}"
fi

EXIT_CODE=$?

echo ""
echo -e "${CYAN}========================================================================${RESET}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✔ System update finished successfully!${RESET}"
else
    echo -e "${YELLOW}⚠ Update process exited with code $EXIT_CODE.${RESET}"
fi
echo -e "${CYAN}========================================================================${RESET}"
echo ""
echo -e "${BOLD}Press [ENTER] to exit...${RESET}"
read -r

# Refresh Waybar update badge
pkill -RTMIN+8 waybar 2>/dev/null || pkill -SIGRTMIN+8 waybar 2>/dev/null || true
