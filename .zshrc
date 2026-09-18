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

# Distro-agnostic plugin paths (Arch & Debian compatible)
for _p in /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh \
          /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh; do
    if [[ -f "$_p" ]]; then
        source "$_p"
        break
    fi
done

for _p in /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh \
          /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh; do
    if [[ -f "$_p" ]]; then
        source "$_p"
        break
    fi
done

ZSH_HIGHLIGHT_STYLES[command]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[alias]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[builtin]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=12,bold'
ZSH_HIGHLIGHT_STYLES[path]='fg=15,bold'
ZSH_HIGHLIGHT_STYLES[single-hyphen-option]='fg=magenta'
ZSH_HIGHLIGHT_STYLES[double-hyphen-option]='fg=magenta'

export PATH="$PATH:$HOME/.local/bin"
