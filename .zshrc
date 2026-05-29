# Path to Oh My Zsh (installed by install.sh into ~/.oh-my-zsh)
export ZSH="$HOME/.oh-my-zsh"

ZSH_THEME="fishy"

# Disable Oh My Zsh update prompts (manage updates yourself)
zstyle ':omz:update' mode disabled

plugins=(git)

if [[ -f "$ZSH/oh-my-zsh.sh" ]]; then
    source "$ZSH/oh-my-zsh.sh"
else
    echo "Oh My Zsh not found at $ZSH — run ./install.sh first." >&2
    PROMPT='%n@%m %~ ❯ '
fi

# Arch Linux plugin paths (must be sourced after oh-my-zsh.sh)
_autosuggestions=/usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
_syntax_highlighting=/usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

[[ -f "$_autosuggestions" ]] && source "$_autosuggestions"
[[ -f "$_syntax_highlighting" ]] && source "$_syntax_highlighting"

ZSH_HIGHLIGHT_STYLES[command]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[alias]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[path]='fg=15,bold'
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=magenta'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=magenta'

export PATH="$PATH:$HOME/.local/bin"
