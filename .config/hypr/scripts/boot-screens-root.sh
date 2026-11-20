#!/bin/sh
# boot-screens-root.sh - put the boot menu and start-up theme in place (run as root by boot-screens.py)
#
#   boot-screens-root.sh install <folder made by boot-screens.py> <WIDTHxHEIGHT>
#   boot-screens-root.sh reset
#
# Only copies the expected image / theme files, never runs anything from that folder.
# Lines it adds to /etc/default/grub end with "# akim-dotfiles"; lines it replaces are kept as
# "#akim-dotfiles-was: ..." so reset puts them back exactly.

set -e
[ "$(id -u)" -eq 0 ] || { echo "boot-screens-root.sh must run as root" >&2; exit 1; }

GRUB_CFG=/etc/default/grub
GRUB_DIR=/boot/grub/themes/akim
PLY_DIR=/usr/share/plymouth/themes/akim
MARK="# akim-dotfiles"
WAS="#akim-dotfiles-was: "
SPLASH_FLAG=/etc/default/grub.akim-splash

have() { command -v "$1" >/dev/null 2>&1; }

copy_files() {   # copy_files <from> <to> <names...>
    from="$1"; to="$2"; shift 2
    rm -rf "$to"
    mkdir -p "$to"
    for f in "$@"; do
        [ -f "$from/$f" ] && [ ! -L "$from/$f" ] && cp "$from/$f" "$to/$f" && chmod 644 "$to/$f"
    done
    return 0
}

undo_grub_lines() {
    [ -f "$GRUB_CFG" ] || return 0
    sed -i "/ $MARK\$/d; s/^$WAS//" "$GRUB_CFG"
    if [ -f "$SPLASH_FLAG" ]; then
        sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\) splash"/\1"/' "$GRUB_CFG"
        rm -f "$SPLASH_FLAG"
    fi
}

case "$1" in
install)
    src="$2"; mode="$3"
    [ -d "$src/grub" ] && [ -d "$src/plymouth" ] || { echo "missing theme folder" >&2; exit 2; }
    printf '%s' "$mode" | grep -Eq '^[0-9]{3,5}x[0-9]{3,5}$' || { echo "bad resolution: $mode" >&2; exit 2; }
    have update-grub || { echo "update-grub not found (only Debian's GRUB is supported)" >&2; exit 3; }

    echo "--> Boot menu..."
    copy_files "$src/grub" "$GRUB_DIR" theme.txt background.png font.pf2 \
        select_nw.png select_n.png select_ne.png select_w.png select_c.png select_e.png select_sw.png select_s.png select_se.png

    undo_grub_lines
    # keep the user's own values commented, then add ours
    sed -i "s/^\(GRUB_THEME=.*\)/$WAS\1/; s/^\(GRUB_GFXMODE=.*\)/$WAS\1/; s/^\(GRUB_TERMINAL=console.*\)/$WAS\1/; s/^\(GRUB_TERMINAL_OUTPUT=console.*\)/$WAS\1/" "$GRUB_CFG"
    {
        echo "GRUB_THEME=\"$GRUB_DIR/theme.txt\" $MARK"
        echo "GRUB_GFXMODE=\"$mode,auto\" $MARK"
    } >> "$GRUB_CFG"

    echo "--> Start-up animation..."
    if ! have plymouth-set-default-theme; then
        apt-get install -y plymouth >/dev/null || { echo "could not install plymouth" >&2; exit 4; }
    fi
    copy_files "$src/plymouth" "$PLY_DIR" akim.plymouth akim.script bg.png ring.png word.png prompt.png bullet.png field.png
    if ! grep -q '^GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\bsplash\b' "$GRUB_CFG"; then
        sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\)"/\1 splash"/' "$GRUB_CFG"
        touch "$SPLASH_FLAG"
    fi
    plymouth-set-default-theme akim
    echo "--> Rebuilding the start-up files (about a minute)..."
    update-initramfs -u >/dev/null
    update-grub >/dev/null 2>&1
    echo "Boot screens installed: you'll see them at the next start."
    ;;
reset)
    undo_grub_lines
    rm -rf "$GRUB_DIR"
    if have plymouth-set-default-theme && [ "$(plymouth-set-default-theme 2>/dev/null)" = akim ]; then
        plymouth-set-default-theme --reset
        rm -rf "$PLY_DIR"
        echo "--> Rebuilding the start-up files (about a minute)..."
        update-initramfs -u >/dev/null
    fi
    rm -rf "$PLY_DIR"
    have update-grub && update-grub >/dev/null 2>&1
    echo "Boot screens back to Debian's."
    ;;
*)
    echo "usage: boot-screens-root.sh install <folder> <WIDTHxHEIGHT> | reset" >&2
    exit 2
    ;;
esac
