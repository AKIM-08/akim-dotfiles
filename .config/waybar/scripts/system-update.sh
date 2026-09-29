#!/usr/bin/env bash
# system-update.sh - Interactive system updater for Debian

BOLD="\033[1m"
GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
CYAN="\033[1;36m"
RED="\033[1;31m"
RESET="\033[0m"

clear
echo -e "${CYAN}========================================================================${RESET}"
echo -e "${BOLD}                     󰅢  DEBIAN SYSTEM UPDATE & UPGRADE                 ${RESET}"
echo -e "${CYAN}========================================================================${RESET}"
echo ""

if command -v nala &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Updating packages with nala...${RESET}"
    echo ""
    sudo nala update && sudo nala upgrade
elif command -v apt &>/dev/null; then
    echo -e "${BLUE}==>${RESET} ${BOLD}Updating packages with APT...${RESET}"
    echo ""
    echo -e "${YELLOW}--> Updating package lists...${RESET}"
    sudo apt update
    echo ""
    echo -e "${YELLOW}--> Upgrading packages...${RESET}"
    sudo apt upgrade
    echo ""
    echo -e "${YELLOW}--> Cleaning unused dependencies...${RESET}"
    sudo apt autoremove -y
else
    echo -e "${RED}Error: APT package manager not found.${RESET}"
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
