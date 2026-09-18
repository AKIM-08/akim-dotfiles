#!/bin/bash
# install/rollback.sh - Revert configuration changes made by akim-dotfiles

set -eo pipefail

echo "=========================================================================="
echo " akim-dotfiles Configuration Rollback Utility"
echo "=========================================================================="

backups=($(find "$HOME/.config" -maxdepth 1 -name "*.backup-before-akim-dotfiles-*" 2>/dev/null))
zsh_backup=$(find "$HOME" -maxdepth 1 -name ".zshrc.backup-before-akim-dotfiles-*" 2>/dev/null | tail -1)

if [ ${#backups[@]} -eq 0 ] && [ -z "$zsh_backup" ]; then
    echo "No akim-dotfiles backup directories found in ~/.config or ~/"
    exit 0
fi

echo "Found the following backups to restore:"
for b in "${backups[@]}"; do
    echo "  - $b"
done
[ -n "$zsh_backup" ] && echo "  - $zsh_backup"

echo ""
read -p "Do you want to restore these backups and revert your current config? (y/N): " choice
case "$choice" in
    [yY][eE][sS]|[yY])
        for b in "${backups[@]}"; do
            original="${b%%.backup-before-akim-dotfiles-*}"
            echo "--> Restoring $original..."
            rm -rf "$original"
            mv "$b" "$original"
        done
        if [ -n "$zsh_backup" ]; then
            original="$HOME/.zshrc"
            echo "--> Restoring $original..."
            rm -f "$original"
            mv "$zsh_backup" "$original"
        fi
        echo "Rollback complete! Your previous configuration has been restored."
        ;;
    *)
        echo "Rollback cancelled."
        ;;
esac
