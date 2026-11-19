# akim.zsh-theme - two-line powerline prompt in the wallpaper's colors
#
#   [ ~/akim-dotfiles ]>[  main ✚1 ●2 …1 ]>   󰔟 4s  ✘ 1
#   ❯
#
# Colored blocks use the terminal palette (colors 1-6 come from pywal, so the prompt follows the
# wallpaper like the rest of the desktop). Shown only when useful: git branch and changes, Python
# venv, how long the last command took (2 s or more), its exit code when it failed, user@host
# over SSH. The arrow turns red after a failed command.

setopt PROMPT_SUBST
zmodload zsh/datetime 2>/dev/null

# Nerd Font glyphs, written as escapes so editors can't mangle them
typeset -g _AKIM_SEP=$'' _AKIM_BRANCH=$'' _AKIM_DIR=$'' _AKIM_PY=$'' _AKIM_ROOT=$'' _AKIM_CAP=$''

typeset -g _AKIM_START=""
typeset -g _AKIM_TOOK=""
typeset -g _AKIM_GIT=""

_akim_preexec() { _AKIM_START=$EPOCHREALTIME }

_akim_took() {
    _AKIM_TOOK=""
    [[ -n $_AKIM_START ]] || return
    local s=$(( ${EPOCHREALTIME%.*} - ${_AKIM_START%.*} ))
    _AKIM_START=""
    (( s < 2 )) && return
    if (( s >= 3600 )); then _AKIM_TOOK="$((s / 3600))h$(( s % 3600 / 60 ))m"
    elif (( s >= 60 )); then _AKIM_TOOK="$((s / 60))m$((s % 60))s"
    else _AKIM_TOOK="${s}s"; fi
}

# Branch and counts from one `git status` call (fast enough for normal repos)
_akim_git() {
    _AKIM_GIT=""
    local out
    out=$(GIT_OPTIONAL_LOCKS=0 command git status --porcelain=v2 --branch 2>/dev/null) || return
    local branch="" ahead=0 behind=0 staged=0 changed=0 untracked=0 conflicts=0 line xy
    for line in "${(@f)out}"; do
        case $line in
            "# branch.head "*) branch=${line#\# branch.head } ;;
            "# branch.oid "*) [[ $branch == "(detached)" ]] && branch=${${line#\# branch.oid }[1,7]} ;;
            "# branch.ab "*) xy=${line#\# branch.ab }; ahead=${${xy%% *}#+}; behind=${${xy##* }#-} ;;
            "? "*) (( untracked++ )) ;;
            "u "*) (( conflicts++ )) ;;
            [12]" "*)
                xy=${line[3,4]}
                [[ ${xy[1]} != "." ]] && (( staged++ ))
                [[ ${xy[2]} != "." ]] && (( changed++ )) ;;
        esac
    done
    [[ $branch == "(detached)" ]] && branch="detached"
    local s="$_AKIM_BRANCH $branch"
    (( ahead ))     && s+=" ⇡$ahead"
    (( behind ))    && s+=" ⇣$behind"
    (( conflicts )) && s+=" ✖$conflicts"
    (( staged ))    && s+=" ✚$staged"
    (( changed ))   && s+=" ●$changed"
    (( untracked )) && s+=" …$untracked"
    _AKIM_GIT=${s//\%/%%}          # a % in a branch name must not become a prompt escape
}

# A block: _akim_seg <color> <text>; joins the previous block with an arrow
_akim_seg() {
    if [[ -n $_akim_prev ]]; then
        _akim_line+="%K{$1}%F{$_akim_prev}$_AKIM_SEP%f"
    else
        _akim_line+="%F{$1}$_AKIM_CAP%f"                # rounded left end
    fi
    _akim_line+="%K{$1}%F{0}%B $2 %b"
    _akim_prev=$1
}

_akim_precmd() {
    _akim_took
    _akim_git
    local _akim_line="" _akim_prev=""

    if [[ -n $SSH_CONNECTION || -n $SSH_TTY ]]; then
        _akim_seg 3 "󰣀 %n@%m"
    elif (( UID == 0 )); then
        _akim_seg 1 "$_AKIM_ROOT root"
    fi
    _akim_seg 4 "$_AKIM_DIR %(4~|…/%3~|%~)"
    [[ -n $VIRTUAL_ENV ]] && _akim_seg 2 "$_AKIM_PY ${VIRTUAL_ENV:t}"
    [[ -n $_AKIM_GIT ]] && _akim_seg 5 "$_AKIM_GIT"
    _akim_line+="%k%F{$_akim_prev}$_AKIM_SEP%f"

    [[ -n $_AKIM_TOOK ]] && _akim_line+="  %F{8}󰔟 $_AKIM_TOOK%f"
    _akim_line+="%(?..  %F{1}✘ %?%f)"         # exit code, only after a failure

    PROMPT="
$_akim_line
%(?.%F{6}.%F{1})❯%f "
}

PROMPT2='%F{8}… %f'
RPROMPT=''

autoload -Uz add-zsh-hook
add-zsh-hook preexec _akim_preexec
add-zsh-hook precmd _akim_precmd
