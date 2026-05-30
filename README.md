# akim-dotfiles

Configuration Hyprland pour **Arch Linux** (laptop, écran unique, clavier **AZERTY**), avec thème dynamique généré depuis le fond d'écran via **pywal16**.

## Stack

| Composant | Outil |
|-----------|-------|
| OS | Arch Linux |
| Écran de connexion | SDDM (thème **akim** — split-screen) |
| Compositrice | Hyprland |
| Terminal | Kitty |
| Barre d'état | Waybar (4 thèmes) |
| Lanceur | Rofi (+ Wofi pour certains menus) |
| Menu d'alimentation | wlogout |
| Notifications | SwayNC |
| Fond d'écran | hyprpaper |
| Verrouillage / veille | hyprlock + hypridle |
| Infos système (terminal) | fastfetch |
| Thème GTK | Catppuccin Mocha + accents **pywal16** (`gtk.css`) |
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
├── sddm/akim/              # Thème SDDM personnalisé (split-screen)
├── omz-custom/             # Thème fishy (copié vers ~/.oh-my-zsh/themes/ à l'install)
│   └── themes/fishy.zsh-theme
├── assets/
│   └── akim-avatar.png     # Avatar hyprlock (copié vers ~/Pictures/)
├── wallpapers/             # Fonds d'écran source (image1 … image8)
└── .config/
    ├── hypr/               # Hyprland, hyprpaper, hyprlock, hypridle + scripts
    ├── waybar/             # Barre + thèmes + scripts
    ├── wlogout/            # Menu d'alimentation
    ├── kitty/              # Terminal
    ├── rofi/               # Lanceur + presse-papier (clipboard.rasi)
    ├── wofi/               # Menus (sélecteur de thème Waybar)
    ├── swaync/             # Centre de notifications
    ├── waypaper/           # Gestionnaire de fonds d'écran (GUI)
    ├── wal/                # Templates pywal16 (Hyprland, GTK)
    ├── gtk-3.0/            # Thème GTK de base (Catppuccin Mocha)
    └── gtk-4.0/            # Thème GTK 4 / libadwaita
```

> `current.jpg` n'est **pas** dans le dépôt : c'est un **symlink** vers une image dans `~/Pictures/wallpapers/` (ex. `image1.jpg`), créé à l'installation. Cela évite de recopier le JPEG et de perdre en qualité.

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
2. Installe les **paquets essentiels** (Hyprland, Kitty, Waybar, wlogout, pipewire-pulse, bluez, btop…)
3. Installe les **applications optionnelles** sans bloquer (Firefox, Discord, VS Code, VLC, OBS, Cava…)
4. Active **NetworkManager** et **bluetooth**
5. Installe **yay** puis depuis l'AUR : pywal16, Catppuccin Mocha GTK, Papirus folders, Nordzy, Waypaper
6. Installe des paquets AUR optionnels (Brave, Spotify, pipes.sh, tty-clock, thème SDDM Catppuccin…)
7. Copie les wallpapers, déploie les configs, configure **wlogout** et les thèmes GTK
8. Installe Oh My Zsh + thème fishy, rend les scripts exécutables
9. Génère le **thème dynamique** depuis `current.jpg` via `apply-pywal-theme.sh`
10. Installe le thème SDDM **akim** et active **SDDM**

Les paquets optionnels peuvent échouer sans interrompre l'installation. Le changement de shell vers zsh affiche un avertissement si `chsh` échoue (mot de passe requis).

### Mise à jour après `git pull`

Sur un PC qui a **déjà** cloné le dépôt et installé les dotfiles :

```bash
cd ~/akim-dotfiles          # adapter le chemin si besoin
git pull

# Déployer les configs
cp -r .config/* ~/.config/
cp .zshrc ~/.zshrc 2>/dev/null || true

# Scripts exécutables
chmod +x ~/.config/hypr/scripts/*.sh
chmod +x ~/.config/hypr/scripts/pywal-fallback.py
chmod +x ~/.config/waybar/scripts/*.sh
chmod +x ~/.config/swaync/refresh.sh
chmod +x ~/.config/waypaper/wallpaper_script.sh
chmod +x ~/.config/wlogout/hibernate.sh

# Paquets ajoutés récemment (sans erreur si déjà installés)
sudo pacman -S --needed --noconfirm pipewire-pulse bluez btop qt6-declarative qt6-quickcontrols2
sudo systemctl enable --now bluetooth 2>/dev/null || true

# Fond d'écran : symlink (qualité préservée)
mkdir -p ~/Pictures/wallpapers
[ -f ~/Pictures/wallpapers/image1.jpg ] && ln -sf ~/Pictures/wallpapers/image1.jpg ~/Pictures/wallpapers/current.jpg

# Thème SDDM akim
sudo mkdir -p /usr/share/sddm/themes/akim
sudo cp -r sddm/akim/* /usr/share/sddm/themes/akim/
sudo cp -L ~/Pictures/wallpapers/current.jpg /usr/share/sddm/themes/akim/background.jpg 2>/dev/null \
  || sudo cp ~/Pictures/wallpapers/image1.jpg /usr/share/sddm/themes/akim/background.jpg 2>/dev/null || true
sudo sed -i 's/^Current=.*/Current=akim/' /etc/sddm.conf.d/akim-dotfiles.conf 2>/dev/null || true
sudo rm -f /etc/sddm.conf.d/akim-dotfiles-theme.conf 2>/dev/null || true

# Tester le thème SDDM (doit afficher "Success" ou aucune erreur QML)
sddm-greeter --test-mode --theme akim

# Régénérer le thème pywal + GTK
~/.config/hypr/scripts/apply-pywal-theme.sh ~/Pictures/wallpapers/current.jpg

# Recharger la session Hyprland
hyprctl reload
pkill waybar; waybar &
swaync-client --reload-css 2>/dev/null || (pkill swaync; swaync &)
```

> **Option rapide** : relancer `./install.sh` depuis le repo fait aussi une grande partie de la mise à jour (paquets, SDDM, pywal). Les commandes ci-dessus évitent une réinstallation complète.

### Écran de connexion (SDDM)

Au démarrage, **SDDM** affiche le thème **akim** : panneau gauche (Welcome, horloge, login, session) et fond d'écran visible à droite.

- **hyprlock** = verrouillage *pendant* la session (hypridle)
- **SDDM** = connexion *au boot*

Changer le fond SDDM :

```bash
sudo cp -L ~/Pictures/wallpapers/current.jpg /usr/share/sddm/themes/akim/background.jpg
```

Avatar (même image que hyprlock) :

```bash
cp ~/Pictures/akim-avatar.png ~/.face
cp ~/Pictures/akim-avatar.png ~/.face.icon
```

À l'écran SDDM : choisir la session **Hyprland (Wayland)** si proposée.

#### SDDM : « Main.qml: No such file » ou thème par défaut

SDDM doit utiliser **`Current=akim`** (nom du thème), **pas** un chemin vers `~/akim-dotfiles/sddm/`.

```bash
cd ~/akim-dotfiles
git pull
~/.config/hypr/scripts/fix-sddm-theme.sh
sudo reboot
```

#### SDDM ne démarre pas / écran noir

1. Voir les logs : `journalctl -u sddm -b --no-pager`
2. Tester le thème : `sddm-greeter --test-mode --theme akim`
3. Si erreur QML ou Wayland, passer en X11 dans `/etc/sddm.conf.d/akim-dotfiles.conf` :
   ```ini
   [General]
   DisplayServer=x11
   ```
4. Réinstaller le thème :
   ```bash
   sudo cp -r ~/akim-dotfiles/sddm/akim/* /usr/share/sddm/themes/akim/
   sudo systemctl restart sddm
   ```

### Manuelle (partielle)

```bash
cp -r .config/* ~/.config/
cp .zshrc ~/.zshrc
cp wallpapers/image*.* ~/Pictures/wallpapers/ 2>/dev/null || true
cp assets/akim-avatar.png ~/Pictures/akim-avatar.png 2>/dev/null || true
ln -sf ~/Pictures/wallpapers/image1.jpg ~/Pictures/wallpapers/current.jpg
chmod +x ~/.config/hypr/scripts/*.sh ~/.config/hypr/scripts/pywal-fallback.py
chmod +x ~/.config/waybar/scripts/*.sh ~/.config/waypaper/wallpaper_script.sh
chmod +x ~/.config/wlogout/hibernate.sh
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
| `Super + Q` | Lanceur d'applications (Rofi) — **toggle** (ouvre / ferme) |
| `Super + A` | Fermer la fenêtre active |
| `Super + F` | Gestionnaire de fichiers (Nautilus) |
| `Super + B` | Navigateur web (Firefox, Brave ou Chromium) |
| `Super + V` | Historique du presse-papier — **toggle** |
| `Super + P` | Capture d'écran **zone** → `~/Pictures/Screenshots/` + presse-papier |
| `Super + Alt + P` | Capture d'écran **plein écran** |
| `Super + Échap` | Menu d'alimentation (wlogout) |
| `Super + N` | Centre de notifications (SwayNC) |
| `Super + D` | Discord |
| `Super + Shift + T` | Changer le thème Waybar |
| `Super + Alt + →` | Fond d'écran suivant + nouveau thème |
| `Super + Alt + ←` | Fond d'écran précédent + nouveau thème |

Les workspaces `Super + &`, `Super + é`, `Super + "`, etc. correspondent aux touches **1–10** sur un clavier AZERTY.

### Centre de notifications (SwayNC)

Widgets : média, notifications, **volume**, **luminosité**, grille de raccourcis :

| Bouton | Action |
|--------|--------|
| Mute sortie | `wpctl` — mute haut-parleurs |
| Mute micro | `wpctl` — mute micro |
| Wi‑Fi | `nmtui` (dans Kitty) |
| Bluetooth | Active BT + ouvre Blueman |
| Lune | Ne pas déranger (toggle) |
| Graphique | `btop` (dans Kitty) |

`Super + N` ou l'icône cloche dans Waybar ouvre / ferme le centre.

### Verrouillage automatique (hypridle)

| Délai | Action |
|-------|--------|
| 10 min | Luminosité écran réduite |
| 15 min | Verrouillage (**hyprlock** + avatar AKIM) + écran éteint |
| 20 min | Mise en veille (suspend) |

**Hibernation à 1 %** (sur batterie, sans secteur) : script `battery-hibernate-watch.sh` (nécessite une partition **swap** active).

### Menu d'alimentation (wlogout)

`Super + Échap` ouvre wlogout (protocole **layer-shell**, grille 2×2 centrée) : **Logout**, **Shutdown**, **Hibernate**, **Reboot**.

> La fenêtre wlogout est **transparente** ; seuls les boutons sont visibles (plus de panneau vide sur le côté).

> **Hibernation** : vérifie la présence d'une partition **swap** active (`swapon --show`). Sans swap, une notification s'affiche et l'action est annulée.

### Thème dynamique (pywal16)

Les couleurs de l'interface sont **extraites automatiquement** depuis `~/Pictures/wallpapers/current.jpg` via pywal16.

Script central : `~/.config/hypr/scripts/apply-pywal-theme.sh`

- Appelé à l'installation, au changement de fond (`Super + Alt + ←/→`), et par Waypaper
- Si pywal16 échoue, `pywal-fallback.py` extrait quand même une palette depuis l'image (Pillow)
- **GTK** : `~/.config/gtk-3.0/gtk.css` et `gtk-4.0/gtk.css` mis à jour depuis pywal (relancer les apps GTK pour voir l'effet)
- **Hyprland** : opacité ~0.93 sur Firefox, Brave, Discord, Telegram, Code, VLC, etc.

Composants mis à jour :

- **Hyprland** — bordures et opacité des fenêtres
- **Kitty** — couleurs du terminal
- **Rofi** — lanceur (icônes Papirus, largeur compacte)
- **Hyprlock** — écran de verrouillage
- **Waybar / SwayNC / wlogout** — via `colors-waybar.css`
- **Cava** — visualiseur audio

`Super + Alt + ←/→` change le fond d'écran et régénère le thème complet.

### Thèmes Waybar

Quatre styles : **default**, **line**, **zen**, **experimental**.

- Raccourci : `Super + Shift + T`
- Ou : `~/.config/waybar/scripts/select.sh`

L'horloge affiche les **secondes** et se met à jour chaque seconde (`interval: 1`).

### Gestionnaire de fonds d'écran (Waypaper)

GUI installée via AUR (`waypaper`). Lancez `waypaper` depuis un terminal ou ajoutez un raccourci. Pointe vers `~/Pictures/wallpapers/` ; chaque changement exécute `wallpaper_script.sh` → `apply-pywal-theme.sh`.

### Ajouter un fond d'écran

1. Nommer le fichier `image9.jpg` (ou suivre la numérotation) dans `wallpapers/` du dépôt ou `~/Pictures/wallpapers/`
2. Parcourir avec `Super + Alt + ←/→`
3. Ou utiliser Waypaper

### Qualité des fonds d'écran (éviter le flou)

- Utilisez des images **au moins aussi grandes que votre écran** (ex. 1920×1080 ou plus pour un laptop FHD).
- `current.jpg` est un **symlink** vers le fichier source (pas de recompression).
- Le mode d'affichage est **`cover`** (remplit l'écran sans étirer).
- Vérifiez l'échelle du moniteur : `hyprctl monitors` — un scale > 1 demande des images plus grandes.
- Les fenêtres **transparentes** floutent le fond derrière elles (effet Hyprland) : ce n'est pas le wallpaper qui est flou.
- **hyprlock** applique volontairement un flou sur l'écran de verrouillage uniquement.

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
| `.config/hypr/hyprland.conf` | Raccourcis, opacité, règles fenêtres |
| `.config/hypr/hypridle.conf` | Délais de verrouillage / veille |
| `.config/gtk-3.0/settings.ini` | Thème GTK Catppuccin Mocha et curseur |
| `.config/gtk-4.0/settings.ini` | Thème GTK 4 pour apps libadwaita |
| `sddm/akim/` | Écran de connexion SDDM |
| `wallpapers/` | Vos propres images |

Le moniteur est configuré en `monitor=,preferred,auto,1` (auto-détection laptop). Pour un écran externe, voir la [doc Hyprland Monitors](https://wiki.hyprland.org/Configuring/Monitors/).

## Dépannage rapide

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `misc:vfr does not exist` | Hyprland trop ancien | `git pull` puis recopier `hyprland.conf` |
| Wi‑Fi Waybar `span color=""` | Icône réseau + couleur vide | `git pull`, recopier `waybar/config` + `style.css` |
| `ERROR: Cannot fetch updates` | `checkupdates` / miroirs pacman | Normal hors ligne ; module pacman vérifie toutes les heures |
| `Discharging` dans le terminal | Bruit waybar / batterie | Sans impact ; ignorable |
| Boutons SwayNC violet clair | GTK par défaut | `apply-pywal-theme.sh` + `swaync-client --reload-css` |
| SDDM cassé | Thème QML invalide | Voir section SDDM ci-dessus |

## Notes

- Ne supprimez pas `current.jpg` : symlink vers le fond actif pour hyprpaper et pywal16.
- Les scripts dans `.config/*/scripts/` doivent être exécutables (`chmod +x`).
- Police unique : **JetBrains Mono Nerd Font** (Kitty, hyprlock, Waybar, SDDM).
- **pywal-discord** (sync thème Discord) : optionnel — `yay -S pywal-discord` si souhaité.
- **Bluetooth** : service `bluetooth` requis ; sans adaptateur, Blueman affichera une erreur.
- **fastfetch** : lancez `fastfetch` dans Kitty pour les infos système.
