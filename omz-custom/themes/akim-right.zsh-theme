# akim-right.zsh-theme - one-line prompt, everything else at the right edge
#
#   <folder> akim-dotfiles ❯ git push          ✘ 1  <timer> 4s  <py> .venv  <branch> main ✚1 ●2 …1
#
# Left: only the current folder's name and the arrow, so commands start early on the line.
# Right edge: the exit code after a failure, how long the last command took (2 s or more), the
# Python venv and the git branch with its changes. It disappears when a long command needs the
# room. The arrow turns red after a failed command; user@host appears over SSH.
# Colors are terminal palette slots, which pywal fills from the wallpaper.
# Switch prompts with `prompt-style blocks|frame|right` (or Settings -> Appearance -> Terminal).

setopt PROMPT_SUBST
zmodload zsh/datetime 2>/dev/null

typeset -g _AKIM_DIR=$'\uf07c' _AKIM_BRANCH=$'\ue0a0' _AKIM_PY=$'\ue73c' _AKIM_TIMER=$'\U000f051f' _AKIM_SSH=$'\U000f08c0'
typeset -g _AKIM_START="" _AKIM_TOOK="" _AKIM_GIT=""
ZLE_RPROMPT_INDENT=0

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
    branch=${branch//\%/%%}
    local s="%F{5}$_AKIM_BRANCH $branch%f" c=""
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
    local left=""
    if [[ -n $SSH_CONNECTION || -n $SSH_TTY ]]; then
        left+="%F{3}%B$_AKIM_SSH %n@%m%b%f "
    elif (( UID == 0 )); then
        left+="%F{1}%Broot%b%f "
    fi
    left+="%F{4}%B$_AKIM_DIR %1~%b%f "
    PROMPT="$left%(?.%F{6}.%F{1})%B❯%b%f "

    local right="%(?..%F{1}%B✘ %?%b%f  )"
    [[ -n $_AKIM_TOOK ]] && right+="%F{8}$_AKIM_TIMER $_AKIM_TOOK%f  "
    [[ -n $VIRTUAL_ENV ]] && right+="%F{2}$_AKIM_PY ${VIRTUAL_ENV:t}%f  "
    [[ -n $_AKIM_GIT ]] && right+="$_AKIM_GIT"
    RPROMPT=${right%  }
}

PROMPT2='%F{8}… %f'

autoload -Uz add-zsh-hook
add-zsh-hook preexec _akim_preexec
add-zsh-hook precmd _akim_precmd
