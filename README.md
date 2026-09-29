# akim-dotfiles

Configuration Hyprland optimisée exclusivement pour **Debian** (13 Trixie, Testing, Sid ou Bookworm backports), pour laptop avec écran unique et clavier **AZERTY**, avec thème dynamique généré depuis le fond d'écran via **pywal16**.

## Stack

| Composant | Outil |
|-----------|-------|
| OS | Debian GNU/Linux (13 Trixie / Testing / Sid ou Bookworm backports) |
| Écran de connexion | GDM / LightDM (coexistence GNOME & session Wayland préservées) |
| Compositrice | Hyprland |
| Terminal | Kitty |
| Barre d'état | Waybar (4 thèmes) |
| Lanceur | Rofi (+ Wofi pour certains menus) |
| Menu d'alimentation | snmenu (radial CS:GO) / wlogout |
| Notifications | SwayNC |
| Fond d'écran | awww (transitions animées) / hyprpaper / waypaper |
| Verrouillage / veille | hyprlock + hypridle |
| Infos système (terminal) | fastfetch |
| Thème GTK | Catppuccin Mocha + accents **pywal16** (`gtk.css`) |
| Couleurs UI | **pywal16** — extraites du fond d'écran actif |
| Curseur | Nordzy |
| Shell | Zsh + Oh My Zsh (thème `fishy`) |

## Structure du dépôt

```
akim-dotfiles/
├── install.sh              # Script d'installation automatisé pour Debian
├── install/
│   ├── debian.sh           # Couche paquets Debian (APT, backports, pipx, thèmes)
│   ├── common.sh           # Déploiement configs, pywal, scripts, sauvegardes
│   └── rollback.sh         # Script de restauration / annulation des modifications
├── .gitignore
├── README.md
├── .zshrc                  # Configuration Zsh (chargement des plugins Debian)
├── omz-custom/             # Thème fishy (copié vers ~/.oh-my-zsh/themes/ à l'install)
│   └── themes/fishy.zsh-theme
├── assets/
│   └── akim-avatar.png     # Avatar hyprlock (copié vers ~/Pictures/)
├── wallpapers/             # Fonds d'écran source (image1 … image8)
└── .config/
    ├── hypr/               # Hyprland, hyprpaper, hyprlock, hypridle + scripts
    ├── waybar/             # Barre + thèmes + scripts
    ├── cpmenu/             # Menu d'alimentation snmenu
    ├── kitty/              # Terminal
    ├── rofi/               # Lanceur + presse-papier (clipboard.rasi)
    ├── wofi/               # Menus (sélecteur de thème Waybar)
    ├── swaync/             # Centre de notifications
    ├── waypaper/           # Gestionnaire de fonds d'écran (GUI)
    ├── wal/                # Templates pywal16 (Hyprland, GTK, Qt)
    ├── gtk-3.0/            # Thème GTK de base (Catppuccin Mocha)
    ├── gtk-4.0/            # Thème GTK 4 / libadwaita
    ├── qt5ct/              # Configuration Qt5
    └── qt6ct/              # Configuration Qt6
```

> `current.jpg` n'est **pas** dans le dépôt : c'est un **symlink** vers une image dans `~/Pictures/wallpapers/` (ex. `image1.jpg`), créé à l'installation. Cela évite de recopier le JPEG et de perdre en qualité.

## Prérequis

- Debian GNU/Linux (Debian 13 Trixie / Sid / Testing recommandé, ou Bookworm avec backports)
- Accès `sudo`
- Connexion internet
- Laptop avec un seul écran (config moniteur auto-détectée)
- GPU Intel/AMD par défaut — **utilisateurs NVIDIA** : décommenter les 2 lignes `env` dans `hyprland.conf` (voir ci-dessous)

## Installation

### Automatique (Recommandé)

```bash
git clone <url-du-repo> akim-dotfiles
cd akim-dotfiles
chmod +x install.sh install/*.sh
./install.sh
```

Options disponibles :
```bash
./install.sh             # Installation standard Debian
./install.sh --rollback  # Restaurer les configurations précédentes
./install.sh --help      # Afficher l'aide
```

### Ce qui est configuré sur Debian :
- **Coexistence GNOME & GDM :** GDM et votre environnement de bureau par défaut restent intacts. La session `Hyprland` est enregistrée dans `/usr/share/wayland-sessions/hyprland.desktop` et disponible depuis le menu de session de GDM (icône engrenage).
- **Sécurité des configurations :** Chaque dossier dans `~/.config/` et `~/.zshrc` est automatiquement sauvegardé (`.backup-before-akim-dotfiles-...`) avant remplacement.
- **Thèmes & Polices :** Les polices JetBrainsMono Nerd Font, le thème GTK Catppuccin Mocha et les curseurs Nordzy sont automatiquement configurés.
- **Outils compilés / pipx :** `pywal16`, `waypaper`, `awww`, et `snmenu` sont installés via pipx et binaires optimisés pour Debian.
- **Authentification PAM :** Configuration `/etc/pam.d/hyprlock` pour le déverrouillage hyprlock avec les identifiants Debian.

### Mise à jour après `git pull`

Sur un PC qui a déjà cloné le dépôt et installé les dotfiles :

```bash
cd ~/akim-dotfiles          # adapter le chemin si besoin
git pull

# Déployer les configs
cp -r .config/* ~/.config/
cp .zshrc ~/.zshrc 2>/dev/null || true

# Rendre les scripts exécutables
chmod +x ~/.config/hypr/scripts/*.sh
chmod +x ~/.config/hypr/scripts/pywal-fallback.py
chmod +x ~/.config/waybar/scripts/*.sh
chmod +x ~/.config/swaync/refresh.sh
chmod +x ~/.config/waypaper/wallpaper_script.sh
chmod +x ~/.config/wlogout/hibernate.sh

# Mettre à jour les paquets Debian si nécessaire
sudo apt update && sudo apt upgrade -y

# Régénérer le thème pywal + GTK
~/.config/hypr/scripts/apply-pywal-theme.sh ~/Pictures/wallpapers/current.jpg

# Recharger la session Hyprland
hyprctl reload
pkill waybar; waybar &
swaync-client --reload-css 2>/dev/null || (pkill swaync; swaync &)
```

> **Option rapide** : relancer `./install.sh` depuis le repo permet d'appliquer rapidement toute mise à jour.

### Connexion et verrouillage

- **GDM / LightDM** = connexion initiale au boot (sélectionnez la session *Hyprland* sur l'écran de login)
- **hyprlock** = verrouillage *pendant* la session (déclenché par hypridle ou le raccourci)

Avatar (utilisé par hyprlock) :
```bash
cp ~/Pictures/akim-avatar.png ~/.face
cp ~/Pictures/akim-avatar.png ~/.face.icon
```

### Installation manuelle (partielle)

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

- **Oh My Zsh** s'installe dans `~/.oh-my-zsh` via `install.sh` (non versionné dans le dépôt).
- **`omz-custom/`** contient le thème `fishy` copié à l'installation.
- **Plugins** : `git` (via OMZ) + `zsh-autosuggestions` + `zsh-syntax-highlighting` (paquets APT Debian, chargés dans l'ordre correct).
- Si OMZ est absent, `.zshrc` affiche un prompt minimal.

## Utilisation

### Raccourcis clavier principaux (AZERTY)

| Raccourci | Action |
|-----------|--------|
| `Super + Entrée` | Ouvrir le terminal (Kitty) |
| `Super + Q` | Lanceur d'applications (Rofi) — **toggle** (ouvre / ferme) |
| `Super + G` | Aide & documentation des raccourcis (**Cheatsheet Rofi**, toggle) |
| `Super + A` | Fermer la fenêtre active |
| `Super + F` | Gestionnaire de fichiers (Nautilus) |
| `Super + B` | Navigateur web (Firefox, Brave ou Chromium) |
| `Super + V` | Historique du presse-papier — **toggle** |
| `Super + P` | Menu capture d'écran / enregistrement (**Rofi**) |
| `Super + Shift + P` | Capture d'écran **zone** → `~/Pictures/Screenshots/` + presse-papier |
| `Super + Alt + P` | Capture d'écran **plein écran** |
| `Super + Shift + R` | Enregistrement vidéo (**wf-recorder**) |
| `Super + Escape` | Menu d'alimentation (**snmenu**) |
| `Super + N` | Centre de notifications (SwayNC) |
| `Super + D` | Discord |
| `Super + Shift + T` | Sélecteur de thème Waybar (**toggle**) |
| `Super + Tab` | Basculer flottant / tuilé |
| `Super + T` | Flottant **centré** (toggle) |
| `Super + S` | Afficher / cacher le **scratchpad** |
| `Super + Shift + S` | Envoyer / retirer la fenêtre du **scratchpad** (toggle) |
| `Super + Alt + →` | Fond d'écran suivant + nouveau thème |
| `Super + Alt + ←` | Fond d'écran précédent + nouveau thème |
| `Super + C` | Mode caféine (**Caffeine toggle**, empêche la veille) |
| `Super + F12` | Menu profil d'alimentation (**Performance / Équilibré / Économie d'énergie**) |

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

**Hibernation à 1 %** (sur batterie, sans secteur) : script `battery-hibernate-watch.sh` (nécessite une partition ou fichier **swap** actif).

### Menu d'alimentation (snmenu)

`Super + Escape` ouvre le menu circulaire **snmenu** : **Logout**, **Shutdown**, **Hibernate**, **Reboot**, **Suspend**, **Lock**.

> **Hibernation** : vérifie la présence d'une partition/fichier **swap** actif (`swapon --show`). Sans swap, une notification s'affiche et l'action est annulée.

### Thème dynamique (pywal16)

Les couleurs de l'interface sont **extraites automatiquement** depuis `~/Pictures/wallpapers/current.jpg` via pywal16.

Script central : `~/.config/hypr/scripts/apply-pywal-theme.sh`

- Appelé à l'installation, au changement de fond (`Super + Alt + ←/→`), et par Waypaper
- Si pywal16 échoue, `pywal-fallback.py` extrait quand même une palette depuis l'image (Pillow)
- **GTK** : `~/.config/gtk-3.0/gtk.css` et `gtk-4.0/gtk.css` mis à jour depuis pywal (relancer les apps GTK pour voir l'effet)
- **Hyprland** : bordures et styles de fenêtres synchronisés

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

GUI installée via pipx (`waypaper`). Lancez `waypaper` depuis un terminal ou ajoutez un raccourci. Pointe vers `~/Pictures/wallpapers/` ; chaque changement exécute `wallpaper_script.sh` → `apply-pywal-theme.sh`.

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

Par défaut, les variables NVIDIA sont **commentées** pour Intel/AMD. Si vous avez un GPU NVIDIA, ouvrez `.config/hypr/hyprland.hl` et décommentez :

```conf
env = LIBVA_DRIVER_NAME,nvidia
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
```

Puis rechargez Hyprland : `hyprctl reload`.

## Personnalisation

| Fichier | À adapter |
|---------|-----------|
| `.config/hypr/hyprland.hl` | Raccourcis, opacité, règles fenêtres |
| `.config/hypr/hypridle.conf` | Délais de verrouillage / veille |
| `.config/gtk-3.0/settings.ini` | Thème GTK Catppuccin Mocha et curseur |
| `.config/gtk-4.0/settings.ini` | Thème GTK 4 pour apps libadwaita |
| `wallpapers/` | Vos propres images |

Le moniteur est configuré en `monitor=,preferred,auto,1` (auto-détection laptop). Pour un écran externe, voir la [doc Hyprland Monitors](https://wiki.hyprland.org/Configuring/Monitors/).

## Dépannage rapide

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `misc:vfr does not exist` | Hyprland trop ancien | `git pull` puis recopier `hyprland.hl` |
| Wi‑Fi Waybar `span color=""` | Icône réseau + couleur vide | `git pull`, recopier `waybar/config` + `style.css` |
| Erreur mise à jour Waybar | APT / Dépôts en cours d'actualisation | Cliquer sur le module ou exécuter `sudo apt update` |
| Boutons SwayNC violet clair | GTK par défaut | `apply-pywal-theme.sh` + `swaync-client --reload-css` |
| Erreur session Wayland GDM | Paquet de session manquant | Vérifier `/usr/share/wayland-sessions/hyprland.desktop` |

## Notes

- Ne supprimez pas `current.jpg` : symlink vers le fond actif pour awww et pywal16.
- Les scripts dans `.config/*/scripts/` doivent être exécutables (`chmod +x`).
- Police unique : **JetBrains Mono Nerd Font** (Kitty, hyprlock, Waybar).
- **Bluetooth** : service `bluetooth` requis (`sudo systemctl enable --now bluetooth`).
- **fastfetch** : lancez `fastfetch` dans Kitty pour les infos système.
