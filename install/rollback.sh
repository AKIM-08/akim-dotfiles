#!/bin/bash
# install/rollback.sh - put back the configuration you had before akim-dotfiles
#
# The installer moves each replaced folder of ~/.config (and ~/.zshrc) to
# "<name>.backup-before-akim-dotfiles-<date>". After several installs there are several
# backups of the same folder: the OLDEST one is what you had before akim-dotfiles, so that is the
# one restored. Newer backups (earlier akim-dotfiles versions) are left where they are.

set -o pipefail

echo "=========================================================================="
echo " akim-dotfiles rollback"
echo "=========================================================================="

declare -A oldest
while IFS= read -r b; do
    original="${b%%.backup-before-akim-dotfiles-*}"
    # Names end with a sortable date (YYYYmmdd_HHMMSS): keep the smallest per original
    if [ -z "${oldest[$original]}" ] || [[ "$b" < "${oldest[$original]}" ]]; then
        oldest[$original]="$b"
    fi
done < <(find "$HOME/.config" "$HOME" -maxdepth 1 -name "*.backup-before-akim-dotfiles-*" 2>/dev/null | sort -u)

if [ ${#oldest[@]} -eq 0 ]; then
    echo "No akim-dotfiles backups found in ~/.config or ~/"
    exit 0
fi

echo "These will be restored (the oldest backup of each):"
for original in "${!oldest[@]}"; do
    echo "  ${oldest[$original]}  ->  $original"
done
echo ""
read -r -p "Replace your current configuration with them? (y/N): " choice
case "$choice" in
    [yY]|[yY][eE][sS])
        for original in "${!oldest[@]}"; do
            echo "--> Restoring $original"
            rm -rf "$original"
            mv "${oldest[$original]}" "$original"
        done
        echo ""
        echo "Done. Log out and back in. Newer backups (if any) were left in place."
        ;;
    *)
        echo "Cancelled, nothing changed."
        ;;
esac
