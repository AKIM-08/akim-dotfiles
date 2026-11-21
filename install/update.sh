#!/usr/bin/env bash
# update.sh (akim-update) - bring the installed dotfiles up to date with GitHub.
#
#   akim-update            pull, copy only the files that changed, restart what needs it
#   akim-update --check    only say whether an update is waiting (nothing is changed)
#   akim-update --dry-run  list the files an update would copy (nothing is changed)
#
# It also updates kitty when it is the official build (install/kitty-latest.sh, kitty-update).
#
# Your settings are never overwritten (theme, bar, shortcuts, apps, lock screen...: the same list
# the installer keeps), and a file removed from the repo is only deleted from ~/.config if you
# never changed it. Packages are not installed here: when the installer itself changed, you are
# told to run ./install.sh again.

set -uo pipefail

SELF=$(readlink -f "${BASH_SOURCE[0]}")
REPO=$(cd "$(dirname "$SELF")/.." && pwd)

# Same list as USER_STATE in install/common.sh: choices made in Settings and your own overrides
USER_STATE=(
    hypr/user-settings.hl hypr/user-apps.hl hypr/user-binds.hl hypr/cursor-theme
    hypr/power-menu-style hypr/wallpaper-transition hypr/wallpaper-picker-style hypr/desktop-extras.json hypr/nightlight hypr/idle.json hypr/boot-screens-auto kitty/opacity.conf hypr/screens.json hypr/overview-style
    hypr/hyprlock/active.conf
    waybar/layout.json
)

if [ -t 1 ]; then B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; D=$'\e[2m'; N=$'\e[0m'; else B= G= Y= R= D= N=; fi
say()  { printf '%s\n' "$*"; }
step() { printf '%s==>%s %s\n' "$B" "$N" "$*"; }
warn() { printf '%s!%s %s\n' "$Y" "$N" "$*"; }
die()  { printf '%sx%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] && die "Run akim-update as your normal user, not with sudo."
cd "$REPO" || die "Can't open $REPO"
git rev-parse --git-dir >/dev/null 2>&1 || die "$REPO is not a git clone of akim-dotfiles."

# Offer the short command: ~/.local/bin/akim-update -> this script
link="$HOME/.local/bin/akim-update"
if [ "$(readlink -f "$link" 2>/dev/null)" != "$SELF" ]; then
    mkdir -p "$HOME/.local/bin" && ln -sf "$SELF" "$link" 2>/dev/null
fi
[ -e "$HOME/.local/bin/kitty-update" ] || ln -sf "$REPO/install/kitty-latest.sh" "$HOME/.local/bin/kitty-update" 2>/dev/null

# kitty's official build (install/kitty-latest.sh) isn't updated by apt: update it here too
update_kitty() {
    [ -x "$HOME/.local/kitty.app/bin/kitty" ] || return 0
    [ -f "$REPO/install/kitty-latest.sh" ] || return 0
    bash "$REPO/install/kitty-latest.sh" --update --quiet || warn "kitty update failed (try: kitty-update)"
}

# Older installers set WaylandEnable=false in GDM, which hides Hyprland from the login screen's
# session menu. Offer to undo it (needs the password, so it asks first; never silently).
check_gdm() {
    local bad=() f
    for f in /etc/gdm3/daemon.conf /etc/gdm3/custom.conf; do
        [ -f "$f" ] && grep -q '^WaylandEnable=false' "$f" && bad+=("$f")
    done
    [ ${#bad[@]} -gt 0 ] || return 0
    warn "The login screen hides Hyprland (WaylandEnable=false in ${bad[*]}), set by an older installer."
    if [ -t 0 ]; then
        printf '  Fix it now? It asks for your password. [Y/n] '
        read -r answer
        case "$answer" in [nN]*) ;; *)
            sudo sed -i 's/^WaylandEnable=false/#WaylandEnable=false/' "${bad[@]}" \
                && say "  ${G}Fixed:${N} Hyprland shows in the session menu after the next restart."
            return 0 ;;
        esac
    fi
    say "  To fix it: sudo sed -i 's/^WaylandEnable=false/#WaylandEnable=false/' ${bad[*]}"
}

# --------------------------------------------------------------------------- phase 1: pull
if [ "${1:-}" != "--apply" ]; then
    mode="${1:-}"
    step "Checking GitHub..."
    git fetch --quiet origin || die "Couldn't reach GitHub (no internet?)."
    branch=$(git rev-parse --abbrev-ref HEAD)
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) || upstream="origin/$branch"
    behind=$(git rev-list --count "HEAD..$upstream" 2>/dev/null || echo 0)
    if [ "$behind" -eq 0 ]; then
        say "${G}Dotfiles already up to date.${N}"
        [ "$mode" = "--check" ] || [ "$mode" = "--dry-run" ] || { update_kitty; check_gdm; }
        exit 0
    fi
    say "$behind new change(s):"
    git --no-pager log --format="  ${D}·${N} %s" "HEAD..$upstream" | head -15
    [ "$mode" = "--check" ] && exit 0
    if [ "$mode" = "--dry-run" ]; then
        step "Files an update would copy:"
        git --no-pager diff --name-status "HEAD" "$upstream" | sed 's/^/  /'
        exit 0
    fi

    old=$(git rev-parse HEAD)
    if ! git merge --ff-only --quiet "$upstream" 2>/dev/null; then
        die "Your copy of the repo has its own changes, so it can't be updated automatically.
  See them with:   cd $REPO && git status
  Keep a copy and update:   git stash && akim-update"
    fi
    # The pull may have changed this very script: carry on with the new version
    exec bash "$REPO/install/update.sh" --apply "$old"
fi

# --------------------------------------------------------------------------- phase 2: apply
old="$2"
new=$(git rev-parse HEAD)

is_state() {
    local f
    for f in "${USER_STATE[@]}"; do [ "$1" = "$f" ] && return 0; done
    return 1
}

pictures=$(xdg-user-dir PICTURES 2>/dev/null)
{ [ -n "$pictures" ] && [ "$pictures" != "$HOME" ]; } || pictures="$HOME/Pictures"

# Where a repo file lives once installed (empty: not copied)
target_of() {
    case "$1" in
        .config/*)            printf '%s' "$HOME/$1" ;;
        .zshrc)               printf '%s' "$HOME/.zshrc" ;;
        omz-custom/themes/*)  [ -d "$HOME/.oh-my-zsh/themes" ] && printf '%s' "$HOME/.oh-my-zsh/themes/${1##*/}" ;;
        wallpapers/*)         printf '%s' "$pictures/wallpapers/${1##*/}" ;;
    esac
}

TILDE="~"
copied=() skipped=() removed=() kept=() installer=false
while IFS=$'\t' read -r status path rest; do
    # Renames come as R100<TAB>old<TAB>new: treat as delete old + add new
    if [[ "$status" == R* ]]; then
        changes=("D	$path" "A	$rest")
    else
        changes=("$status	$path")
    fi
    for c in "${changes[@]}"; do
        st=${c%%	*}; f=${c#*	}
        case "$f" in install/update.sh|install/rollback.sh|install/kitty-latest.sh) continue ;; install/*|install.sh) installer=true; continue ;; esac
        dest=$(target_of "$f")
        [ -n "$dest" ] || continue
        rel=${f#.config/}
        if [[ "$f" == .config/* ]] && is_state "$rel" && [ -e "$dest" ]; then
            skipped+=("$rel"); continue
        fi
        if [ -L "$dest" ]; then                 # a link made by the theme (cava, cpmenu...): leave it
            skipped+=("${dest/#$HOME/$TILDE}"); continue
        fi
        if [ "$st" = D ]; then
            [ -f "$dest" ] || continue
            if git show "$old:$f" 2>/dev/null | cmp -s - "$dest"; then
                rm -f "$dest"
                removed+=("${dest/#$HOME/$TILDE}")
            else
                kept+=("${dest/#$HOME/$TILDE}")
            fi
        else
            mkdir -p "$(dirname "$dest")"
            cp "$f" "$dest" || { warn "Couldn't copy $f"; continue; }
            case "$dest" in *.sh|*.py) chmod +x "$dest" ;; esac
            copied+=("$f")
        fi
    done
done < <(git diff --name-status -M "$old" "$new")

step "Updated ${#copied[@]} file(s)"
for f in "${copied[@]}"; do say "  ${D}·${N} $f"; done
for f in "${removed[@]}"; do say "  ${D}· removed${N} $f"; done
for f in "${skipped[@]}"; do say "  ${D}· kept your${N} $f"; done
for f in "${kept[@]}"; do warn "$f is gone from the repo but you changed it, so it was kept"; done

changed() { local p; for p in "${copied[@]}" "${removed[@]}"; do [[ "$p" == *$1* ]] && return 0; done; return 1; }

# --------------------------------------------------------------------------- restart what needs it
running() { pgrep -f "$1" >/dev/null 2>&1; }
restarted=()

# The same fix-ups the installer does after copying
for f in "$HOME/.config/waypaper/config.ini" "$HOME/.config/swappy/config"; do
    [ -f "$f" ] && sed -i -e "s|~/Pictures|$pictures|g" -e "s|\$HOME/Pictures|$pictures|g" "$f"
done
touch "$HOME/.config/hypr/user-settings.hl" "$HOME/.config/hypr/user-apps.hl" "$HOME/.config/hypr/user-binds.hl"
python3 "$HOME/.config/hypr/scripts/apply-papirus-color.py" >/dev/null 2>&1 &

if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
    if changed waybar/ || changed scripts/island.py; then
        python3 "$HOME/.config/waybar/scripts/layout.py" >/dev/null 2>&1
        setsid -f "$HOME/.config/waybar/scripts/launch.sh" >/dev/null 2>&1
        restarted+=("bar")
    fi
    if changed swaync/; then
        swaync-client -R >/dev/null 2>&1; swaync-client -rs >/dev/null 2>&1
        restarted+=("notifications")
    fi
    if changed scripts/idle.py; then
        python3 "$HOME/.config/hypr/scripts/idle.py" start >/dev/null 2>&1
        restarted+=("idle times")
    fi
    if changed scripts/desktop-extras.py; then
        setsid -f python3 "$HOME/.config/hypr/scripts/desktop-extras.py" >/dev/null 2>&1
        restarted+=("desktop widgets")
    fi
    if changed kitty/; then
        pkill -USR1 -x kitty 2>/dev/null && restarted+=("kitty")
    fi
    if changed wal/templates || changed apply-pywal-theme.sh; then
        cur="$pictures/wallpapers/current.jpg"
        [ -e "$cur" ] && setsid -f "$HOME/.config/hypr/scripts/apply-pywal-theme.sh" "$(readlink -f "$cur")" >/dev/null 2>&1 \
            && restarted+=("colors")
    fi
    # Hyprland reloads its own config when the files change; check it is still valid
    sleep 1
    hyprctl reload >/dev/null 2>&1
    errors=$(hyprctl configerrors 2>/dev/null | grep -v '^\s*$')
    if [ -n "$errors" ]; then
        warn "Hyprland reports a problem in its config:"
        printf '%s\n' "$errors" | sed 's/^/    /'
        say  "    (often a line in user-settings.hl / user-binds.hl that a new version no longer accepts)"
    fi
fi

[ ${#restarted[@]} -gt 0 ] && say "Restarted: $(IFS=,; printf '%s' "${restarted[*]}" | sed 's/,/, /g')"
changed .zshrc || changed omz-custom && say "Open a new terminal for the shell changes."
changed scripts/settings.py && running "scripts/settings.py" && say "Close and reopen Settings to see its changes."
$installer && warn "The installer changed too (new packages or system setup). When you have a moment:
    cd $REPO && ./install.sh"
update_kitty
check_gdm
say "${G}Done.${N}"
