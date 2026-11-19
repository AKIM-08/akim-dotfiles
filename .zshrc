# Path to Oh My Zsh (installed by install.sh into ~/.oh-my-zsh)
export ZSH="$HOME/.oh-my-zsh"

# Prompt, in the wallpaper's colors (omz-custom/themes/akim-*.zsh-theme):
#   blocks  colored blocks joined by arrows, two lines
#   frame   ╭─ folder via venv on branch / ╰─❯, status at the right edge (default)
#   right   one line: folder ❯, everything else at the right edge
# Change it with `prompt-style blocks|frame|right` or Settings -> Appearance -> Terminal.
_akim_style=""
[[ -r "$HOME/.config/zsh-prompt-style" ]] && _akim_style=$(<"$HOME/.config/zsh-prompt-style")
_akim_style=${_akim_style//[[:space:]]/}
[[ $_akim_style == (blocks|frame|right) ]] || _akim_style=frame
ZSH_THEME="akim-$_akim_style"
[[ -f "$ZSH/themes/$ZSH_THEME.zsh-theme" || -f "$ZSH/custom/themes/$ZSH_THEME.zsh-theme" ]] || ZSH_THEME="fishy"

# Disable Oh My Zsh update prompts (manage updates yourself)
zstyle ':omz:update' mode disabled

# Plugins that ship with Oh My Zsh (no download needed):
#   git                  aliases: gst, gco, gcm, gl, gp, glog ...
#   sudo                 press Esc twice to put sudo in front of the command
#   extract              `extract file.zip|tar.gz|7z|...` unpacks anything
#   colored-man-pages    readable man pages
#   command-not-found    suggests the package when a command is missing
#   history-substring-search   type part of a command, then Up/Down to cycle matching ones
#   copypath / copyfile  copy the current path / a file's content to the clipboard
plugins=(git sudo extract colored-man-pages command-not-found history-substring-search copypath copyfile)
# Optional tools, enabled when installed
command -v fzf &>/dev/null && plugins+=(fzf)            # Ctrl+R history search, Ctrl+T files, Alt+C dirs
command -v zoxide &>/dev/null && plugins+=(zoxide)      # `z part-of-a-dir` jumps there

if [[ -f "$ZSH/oh-my-zsh.sh" ]]; then
    source "$ZSH/oh-my-zsh.sh"
else
    echo "Oh My Zsh not found at $ZSH — run ./install.sh first." >&2
    PROMPT='%n@%m %~ ❯ '
fi

# ---------------------------------------------------------------- history
HISTFILE="$HOME/.zsh_history"
HISTSIZE=50000
SAVEHIST=50000
setopt EXTENDED_HISTORY HIST_IGNORE_ALL_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS SHARE_HISTORY

# ---------------------------------------------------------------- completion
# Case-insensitive, menu you can move through with the arrows, colored like `ls`
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'r:|=*' 'l:|=* r:|=*'
zstyle ':completion:*' menu select
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format '%F{4}── %d ──%f'
zstyle ':completion:*' group-name ''
setopt AUTO_CD             # type a folder name to go there
setopt INTERACTIVE_COMMENTS

# ---------------------------------------------------------------- plugins from APT
for _p in /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh \
          /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh; do
    if [[ -f "$_p" ]]; then
        source "$_p"
        break
    fi
done
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=8'
ZSH_AUTOSUGGEST_STRATEGY=(history completion)
bindkey '^ ' autosuggest-accept        # Ctrl+Space accepts the grey suggestion (→ works too)

for _p in /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh \
          /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh; do
    if [[ -f "$_p" ]]; then
        source "$_p"
        break
    fi
done
unset _p

# Colors are palette numbers, so they follow the wallpaper too
ZSH_HIGHLIGHT_STYLES[command]='fg=4,bold'
ZSH_HIGHLIGHT_STYLES[alias]='fg=4,bold'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=4,bold'
ZSH_HIGHLIGHT_STYLES[function]='fg=4,bold'
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=5,bold'
ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=1,bold'
ZSH_HIGHLIGHT_STYLES[path]='fg=15,underline'
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=6'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=6'
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=3'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=3'
ZSH_HIGHLIGHT_STYLES[comment]='fg=8'

# history-substring-search: Up/Down cycle the commands containing what you typed
bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down
bindkey '^[OA' history-substring-search-up        # same keys in "application" mode
bindkey '^[OB' history-substring-search-down
HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND='bg=4,fg=0,bold'

# ---------------------------------------------------------------- nicer tools (when installed)
if command -v eza &>/dev/null; then
    alias ls='eza --icons=auto --group-directories-first'
    alias ll='eza -l --icons=auto --group-directories-first --git --time-style=relative'
    alias la='eza -la --icons=auto --group-directories-first --git --time-style=relative'
    alias lt='eza --tree --level=2 --icons=auto'
else
    alias ll='ls -lh --color=auto'
    alias la='ls -lAh --color=auto'
fi
command -v batcat &>/dev/null && ! command -v bat &>/dev/null && alias bat='batcat'   # Debian's name
command -v fdfind &>/dev/null && ! command -v fd &>/dev/null && alias fd='fdfind'
# tty-clock: centered, in the wallpaper's accent (palette color 1, the same as cava and the
# bar). Its default is color 2, which is a different hue on every wallpaper. Options you pass
# still win (e.g. `tty-clock -C 4`).
tty-clock() { command tty-clock -c -C 1 "$@"; }

# prompt-style blocks|frame|right: switch the prompt (this terminal reloads; others on their next start)
prompt-style() {
    case $1 in
        blocks|frame|right)
            mkdir -p "$HOME/.config"
            print -r -- "$1" > "$HOME/.config/zsh-prompt-style"
            exec zsh ;;
        *)
            print "Usage: prompt-style blocks|frame|right   (now: $_akim_style)"
            return 1 ;;
    esac
}

alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'

export PATH="$PATH:$HOME/.local/bin"
export TERMINAL="kitty"

# Launch Hyprland via wrapper script if present (avoids "started without start-hyprland" warning)
if command -v start-hyprland &>/dev/null; then
    alias hyprland='start-hyprland'
    alias Hyprland='start-hyprland'
fi
