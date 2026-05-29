# akim-dotfiles

Configuration Hyprland pour **Arch Linux** (laptop, écran unique, clavier **AZERTY**), avec thème dynamique généré depuis le fond d'écran via **pywal16**.

## Stack

| Composant | Outil |
|-----------|-------|
| OS | Arch Linux |
| Écran de connexion | SDDM (avatar + mot de passe) |
| Compositrice | Hyprland |
| Terminal | Kitty |
| Barre d'état | Waybar (4 thèmes) |
| Lanceur | Rofi (+ Wofi pour certains menus) |
| Menu d'alimentation | wlogout |
| Notifications | SwayNC |
| Fond d'écran | hyprpaper |
| Verrouillage / veille | hyprlock + hypridle |
| Infos système (terminal) | fastfetch |
| Thème GTK | Catppuccin Mocha + Papirus-Dark (apps GTK uniquement) |
| Couleurs UI | **pywal16** — extraites du fond d'écran actif |
| Curseur | Nordzy |
| Shell | Zsh + Oh My Zsh (thème `fishy`) |

## Structure du dépôt

```
akim-dotfiles/
├── install.sh              # Installation automatique (Arch)
├── .gitignore
├── README.md
├── .zshrc
├── omz-custom/             # Thème fishy (copié vers ~/.oh-my-zsh/themes/ à l'install)
│   └── themes/fishy.zsh-theme
├── assets/
│   └── akim-avatar.png     # Avatar hyprlock (copié vers ~/Pictures/)
├── wallpapers/             # Fonds d'écran source (image1 … image8)
└── .config/
    ├── hypr/               # Hyprland, hyprpaper, hyprlock, hypridle
    ├── waybar/             # Barre + thèmes + scripts
    ├── wlogout/            # Menu d'alimentation
    ├── kitty/              # Terminal
    ├── rofi/               # Lanceur d'applications
    ├── wofi/               # Menus (sélecteur de thème Waybar)
    ├── swaync/             # Centre de notifications
    ├── waypaper/           # Gestionnaire de fonds d'écran (GUI)
    ├── wal/templates/      # Template pywal16 pour Hyprland
    ├── gtk-3.0/            # Thème GTK (Catppuccin Mocha)
    └── gtk-4.0/            # Thème GTK 4 / libadwaita
```

> `current.jpg` n'est **pas** dans le dépôt : il est créé à l'installation dans `~/Pictures/wallpapers/` à partir de `image1.jpg` et mis à jour lors du changement de fond d'écran.

## Fonds d'écran inclus

| Fichier | Description |
|---------|-------------|
| `image1.jpg` | Dragon Ball — Goku sur Shenron (fond par défaut) |
| `image2.jpg` | Logo Arch Linux (minimaliste) |
| `image3.jpg` | Paysage arctique — brise-glace |
| `image4.jpg` | Hunter × Hunter — personnages en costume |
| `image5.jpg` | Jujutsu Kaisen — Gojo |
| `image6.jpg` | Dark fantasy — chevalier spectral |
| `image7.jpg` | Montagnes enneigées — Patagonie |
| `image8.jpg` | Sword Art Online — Kirito & Asuna |

## Prérequis

- Arch Linux (installation fraîche ou existante)
- Accès `sudo`
- Connexion internet
- Laptop avec un seul écran (config moniteur auto-détectée)
- GPU Intel/AMD par défaut — **utilisateurs NVIDIA** : décommenter les 2 lignes `env` dans `hyprland.conf` (voir ci-dessous)

## Installation

### Automatique (recommandée)

```bash
git clone <url-du-repo> akim-dotfiles
cd akim-dotfiles
chmod +x install.sh
./install.sh
sudo reboot
```

Le script `install.sh` :

1. Configure la locale en `en_US.UTF-8`
2. Installe les **paquets essentiels** (Hyprland, Kitty, Waybar, wlogout, GTK3, Papirus, libnotify…)
3. Installe les **applications optionnelles** sans bloquer (Firefox, Discord, VS Code, VLC, OBS, Cava…)
4. Active **NetworkManager**
5. Installe **yay** puis depuis l'AUR : pywal16, Catppuccin Mocha GTK, Papirus folders, Nordzy, Waypaper
6. Installe des paquets AUR optionnels (Brave, Spotify, pipes.sh, tty-clock)
7. Copie les wallpapers, déploie les configs, configure **wlogout** et les thèmes GTK
8. Installe Oh My Zsh + thème fishy, rend les scripts exécutables
9. Génère le **thème dynamique** depuis `current.jpg` via `apply-pywal-theme.sh`
10. Active **SDDM** (écran de connexion graphique avec avatar, session Hyprland)

Les paquets optionnels peuvent échouer sans interrompre l'installation. Le changement de shell vers zsh affiche un avertissement si `chsh` échoue (mot de passe requis).

### Écran de connexion (SDDM)

Au démarrage, **SDDM** affiche un écran graphique : avatar (`~/.face`), nom d'utilisateur et mot de passe. Après connexion, la session **Hyprland** démarre.

- **hyprlock** = verrouillage *pendant* la session (Super + veille, ou hypridle)
- **SDDM** = connexion *au boot* (remplace le TTY)

Configuration manuelle :

```bash
# Installer SDDM
sudo pacman -S sddm qt6-multimedia

# Avatar (même image que hyprlock)
cp ~/Pictures/akim-avatar.png ~/.face
cp ~/Pictures/akim-avatar.png ~/.face.icon

# Thème Catppuccin (optionnel)
yay -S catppuccin-sddm-corners-mocha

# Activer SDDM
sudo systemctl enable sddm.service

# Supprimer autologin TTY si configuré avant
sudo rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
rm -f ~/.zprofile

sudo reboot
```

À l'écran SDDM : choisir la session **Hyprland (Wayland)** si proposée.

### Manuelle (partielle)

```bash
# Prérequis : Oh My Zsh + paquets zsh (voir install.sh)
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
cp omz-custom/themes/fishy.zsh-theme ~/.oh-my-zsh/themes/

cp -r .config/* ~/.config/
cp .zshrc ~/.zshrc
cp wallpapers/image*.* ~/Pictures/wallpapers/
cp assets/akim-avatar.png ~/Pictures/akim-avatar.png
cp ~/Pictures/wallpapers/image1.jpg ~/Pictures/wallpapers/current.jpg
chmod +x ~/.config/hypr/scripts/*.sh ~/.config/hypr/scripts/pywal-fallback.py
chmod +x ~/.config/waypaper/wallpaper_script.sh ~/.config/wlogout/hibernate.sh
~/.config/hypr/scripts/apply-pywal-theme.sh ~/Pictures/wallpapers/current.jpg
```

### Shell (Zsh + Oh My Zsh)

- **Oh My Zsh** s'installe dans `~/.oh-my-zsh` via `install.sh` (pas versionné dans le dépôt).
- **`omz-custom/`** contient uniquement le thème `fishy` copié à l'installation.
- **Plugins** : `git` (via OMZ) + `zsh-autosuggestions` + `zsh-syntax-highlighting` (paquets Arch, chargés dans l'ordre correct).
- Si OMZ est absent, `.zshrc` affiche un prompt minimal et un message d'erreur.

## Utilisation

### Raccourcis clavier principaux (AZERTY)

| Raccourci | Action |
|-----------|--------|
| `Super + Entrée` | Ouvrir le terminal (Kitty) |
| `Super + Q` | Fermer la fenêtre active |
| `Super + A` | Lanceur d'applications (Rofi) |
| `Super + F` | Gestionnaire de fichiers (Nautilus) |
| `Super + V` | Historique du presse-papier |
| `Super + N` | Centre de notifications (SwayNC) |
| `Super + D` | Discord |
| `Super + Shift + A` | Capture zone → `~/Pictures/Screenshots/` + presse-papier |
| `Super + Impr. écran` | Capture zone (même raccourci alternatif) |
| `Impr. écran` | Capture écran entier → `~/Pictures/Screenshots/` |
| `Super + Shift + E` | Menu d'alimentation (wlogout) |
| `Super + Shift + T` | Changer le thème Waybar |
| `Super + Alt + →` | Fond d'écran suivant + nouveau thème |
| `Super + Alt + ←` | Fond d'écran précédent + nouveau thème |

Les workspaces `Super + &`, `Super + é`, `Super + "`, etc. correspondent aux touches **1–10** sur un clavier AZERTY.

### Verrouillage automatique (hypridle)

| Délai | Action |
|-------|--------|
| 2 min 30 | Luminosité écran réduite |
| 5 min | Verrouillage (hyprlock + avatar AKIM) |
| 5 min 30 | Écran éteint |
| 30 min | Mise en veille |

### Menu d'alimentation (wlogout)

`Super + Shift + E` ouvre wlogout (protocole **layer-shell**, requis sur Hyprland) avec : **Logout**, **Shutdown**, **Hibernate**, **Reboot**.

> **Hibernation** : vérifie la présence d'une partition **swap** active (`swapon --show`). Sans swap, une notification s'affiche et l'action est annulée.

### Thème dynamique (pywal16)

Les couleurs de l'interface (Hyprland, Waybar, Kitty, Rofi, Hyprlock, SwayNC, wlogout, Cava) sont **extraites automatiquement** depuis `~/Pictures/wallpapers/current.jpg` via pywal16.

Script central : `~/.config/hypr/scripts/apply-pywal-theme.sh`

- Appelé à l'installation, au changement de fond (`Super + Alt + ←/→`), et par Waypaper
- Si pywal16 échoue, `pywal-fallback.py` extrait quand même une palette depuis l'image (Pillow)
- Catppuccin Mocha ne concerne que les **apps GTK** (Nautilus, LibreOffice…) — pas la barre ni le compositor

Composants mis à jour :

- **Hyprland** — bordures de fenêtres
- **Kitty** — couleurs du terminal
- **Rofi** — lanceur
- **Hyprlock** — écran de verrouillage
- **Waybar / SwayNC / wlogout** — via `colors-waybar.css`
- **Cava** — visualiseur audio

`Super + Alt + ←/→` change le fond d'écran et régénère le thème complet.

### Thèmes Waybar

Quatre styles : **default**, **line**, **zen**, **experimental**.

- Raccourci : `Super + Shift + T`
- Ou : `~/.config/waybar/scripts/select.sh`

### Gestionnaire de fonds d'écran (Waypaper)

GUI installée via AUR (`waypaper`). Lancez `waypaper` depuis un terminal ou ajoutez un raccourci. Pointe vers `~/Pictures/wallpapers/` ; chaque changement exécute `wallpaper_script.sh` → `apply-pywal-theme.sh`.

### Ajouter un fond d'écran

1. Nommer le fichier `image9.jpg` (ou suivre la numérotation) dans `wallpapers/` du dépôt ou `~/Pictures/wallpapers/`
2. Parcourir avec `Super + Alt + ←/→`
3. Ou utiliser Waypaper

### Qualité des fonds d'écran (éviter le flou)

- Utilisez des images **au moins aussi grandes que votre écran** (ex. 1920×1080 ou plus pour un laptop FHD).
- Le mode d'affichage est **`cover`** (remplit l'écran sans étirer) — ne pas utiliser `fill` dans Waypaper/hyprpaper, qui déforme et floute l'image.
- Mettez à jour hyprpaper : `sudo pacman -Syu hyprpaper`
- Vérifiez l'échelle du moniteur : `hyprctl monitors` — un scale > 1 (ex. 1.25) demande des images plus grandes.
- **hyprlock** applique volontairement un flou sur l'écran de verrouillage uniquement, pas sur le bureau.

## GPU NVIDIA (optionnel)

Par défaut, les variables NVIDIA sont **commentées** pour Intel/AMD. Si vous avez un GPU NVIDIA, ouvrez `.config/hypr/hyprland.conf` et décommentez :

```conf
env = LIBVA_DRIVER_NAME,nvidia
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
```

Puis rechargez Hyprland : `hyprctl reload`.

## Personnalisation

| Fichier | À adapter |
|---------|-----------|
| `.config/hypr/hyprland.conf` | Variables NVIDIA (si besoin), raccourcis |
| `.config/hypr/hypridle.conf` | Délais de verrouillage / veille |
| `.config/gtk-3.0/settings.ini` | Thème GTK Catppuccin Mocha et curseur |
| `.config/gtk-4.0/settings.ini` | Thème GTK 4 pour apps libadwaita |
| `wallpapers/` | Vos propres images |

Le moniteur est configuré en `monitor=,preferred,auto,1` (auto-détection laptop). Pour un écran externe, voir la [doc Hyprland Monitors](https://wiki.hyprland.org/Configuring/Monitors/).

## Notes

- Ne renommez pas `current.jpg` : c'est le fond actif pour hyprpaper et pywal16 (ignoré par git via `.gitignore`).
- Les scripts dans `.config/*/scripts/` doivent être exécutables (`chmod +x`).
- Police unique : **JetBrains Mono Nerd Font** (Kitty, hyprlock, Waybar).
- **pywal-discord** (sync thème Discord) : optionnel — `yay -S pywal-discord` si souhaité ; le script l'appelle uniquement s'il est installé.
- Les noms de thèmes GTK sont **auto-détectés** à l'installation (Catppuccin Mocha) ; vérifiez `~/.config/gtk-3.0/settings.ini` si un thème ne s'applique pas.
- Horloge Waybar : rafraîchissement toutes les **30 secondes** (compromis batterie / précision).
- **fastfetch** : lancez `fastfetch` dans Kitty pour les infos système (installé par `install.sh`).
