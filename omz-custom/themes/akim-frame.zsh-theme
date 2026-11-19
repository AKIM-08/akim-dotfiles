# akim-frame.zsh-theme - framed two-line prompt with status on the right, in the wallpaper's colors
#
#   ╭─ <folder> ~/akim-dotfiles via <py> .venv on <branch> main ✚1 ●2 …1
#   ╰─❯ git push                                          ✘ 1  <timer> 4s  20:48
#
# First line: the folder, then (when there is one) the Python venv and the git branch with its
# changes, joined by words. Right edge of the input line: the exit code after a failure, how long
# the last command took (2 s or more) and the time; it disappears when a long command needs the
# room. The arrow turns red after a failed command. user@host appears over SSH.
# Colors are terminal palette slots, which pywal fills from the wallpaper.

# Switch prompts with `prompt-style blocks|frame|right` (or Settings -> Appearance -> Terminal).

setopt PROMPT_SUBST
zmodload zsh/datetime 2>/dev/null

# Nerd Font glyphs, written as escapes so editors can't mangle them
typeset -g _AKIM_DIR=$'\uf07c' _AKIM_BRANCH=$'\ue0a0' _AKIM_PY=$'\ue73c' _AKIM_TIMER=$'\U000f051f' _AKIM_SSH=$'\U000f08c0'

typeset -g _AKIM_START="" _AKIM_TOOK="" _AKIM_GIT=""
ZLE_RPROMPT_INDENT=0          # the right side touches the window edge

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

# Branch and counts from one `git status` call
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
    branch=${branch//\%/%%}       # a % in a branch name must not become a prompt escape
    local s="%F{8}on%f %F{5}%B$_AKIM_BRANCH $branch%b%f"
    local c=""
    (( ahead ))     && c+=" ⇡$ahead"
    (( behind ))    && c+=" ⇣$behind"
    (( conflicts )) && c+=" ✖$conflicts"
    (( staged ))    && c+=" ✚$staged"
    (( changed ))   && c+=" ●$changed"
    (( untracked )) && c+=" …$untracked"
    [[ -n $c ]] && s+="%F{3}$c%f"
    _AKIM_GIT=$s
}

_akim_precmd() {
    _akim_took
    _akim_git
    local top="%F{8}╭─%f "
    if [[ -n $SSH_CONNECTION || -n $SSH_TTY ]]; then
        top+="%F{3}%B$_AKIM_SSH %n@%m%b%f %F{8}in%f "
    elif (( UID == 0 )); then
        top+="%F{1}%Broot%b%f %F{8}in%f "
    fi
    top+="%F{4}%B$_AKIM_DIR %(4~|…/%3~|%~)%b%f"
    [[ -n $VIRTUAL_ENV ]] && top+=" %F{8}via%f %F{2}$_AKIM_PY ${VIRTUAL_ENV:t}%f"
    [[ -n $_AKIM_GIT ]] && top+=" $_AKIM_GIT"

    PROMPT="
$top
%F{8}╰─%f%(?.%F{6}.%F{1})%B❯%b%f "

    local right="%(?..%F{1}%B✘ %?%b%f  )"
    [[ -n $_AKIM_TOOK ]] && right+="%F{8}$_AKIM_TIMER $_AKIM_TOOK%f  "
    right+="%F{8}%D{%H:%M}%f"
    RPROMPT=$right
}

PROMPT2='%F{8}   … %f'

autoload -Uz add-zsh-hook
add-zsh-hook preexec _akim_preexec
add-zsh-hook precmd _akim_precmd
