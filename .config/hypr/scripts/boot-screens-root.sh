#!/bin/sh
# boot-screens-root.sh - put the boot menu and start-up theme in place (run as root by boot-screens.py)
#
#   boot-screens-root.sh install <folder made by boot-screens.py> <WIDTHxHEIGHT>
#   boot-screens-root.sh reset                 (also removes the auto-follow rule)
#   boot-screens-root.sh auto-on <user>        let <user> run "install" and "reset" without a
#                                              password: a root-owned copy of this script in
#                                              /usr/local/lib/akim-dotfiles + a sudo rule for it only
#   boot-screens-root.sh auto-off              remove that copy and rule
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
INSTALLED=/usr/local/lib/akim-dotfiles/boot-screens-root.sh
SUDOERS=/etc/sudoers.d/akim-boot-screens

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

auto_off() { rm -f "$SUDOERS" "$INSTALLED"; rmdir /usr/local/lib/akim-dotfiles 2>/dev/null || true; }

case "$1" in
install)
    src="$2"; mode="$3"
    # Through the password-free rule: only the folders boot-screens.py makes in /tmp
    if [ -n "${SUDO_USER:-}" ] && [ "$0" = "$INSTALLED" ]; then
        case "$src" in /tmp/boot-screens-*) ;; *) echo "refused: $src" >&2; exit 2 ;; esac
        case "$src" in *..*) echo "refused: $src" >&2; exit 2 ;; esac
        [ -L "$src" ] && { echo "refused: $src" >&2; exit 2; }
    fi
    # keep the root-owned copy current when following the wallpaper
    if [ -f "$INSTALLED" ] && [ "$0" != "$INSTALLED" ]; then cp "$0" "$INSTALLED"; chmod 755 "$INSTALLED"; fi
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
    auto_off
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
auto-on)
    user="$2"
    printf '%s' "$user" | grep -Eq '^[a-z_][a-z0-9_-]*$' && id "$user" >/dev/null 2>&1 \
        || { echo "unknown user: $user" >&2; exit 2; }
    mkdir -p /usr/local/lib/akim-dotfiles
    cp "$0" "$INSTALLED"
    chown root:root "$INSTALLED"; chmod 755 "$INSTALLED"
    tmp=$(mktemp)
    {
        echo "# akim-dotfiles: the boot screens follow the wallpaper (Settings -> Wallpaper -> Boot screens)."
        echo "# Allows only the root-owned $INSTALLED: \"install\" from /tmp/boot-screens-*, and \"reset\"."
        echo "$user ALL=(root) NOPASSWD: /bin/sh $INSTALLED install /tmp/boot-screens-* *, /bin/sh $INSTALLED reset"
    } > "$tmp"
    if visudo -cf "$tmp" >/dev/null; then
        install -m 440 -o root -g root "$tmp" "$SUDOERS"
        rm -f "$tmp"
        echo "The boot screens now follow your wallpaper."
    else
        rm -f "$tmp"
        echo "could not create the sudo rule" >&2
        exit 5
    fi
    ;;
auto-off)
    auto_off
    echo "The boot screens no longer follow your wallpaper."
    ;;
*)
    echo "usage: boot-screens-root.sh install <folder> <WIDTHxHEIGHT> | reset | auto-on <user> | auto-off" >&2
    exit 2
    ;;
esac
