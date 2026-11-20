# akim-dotfiles

A Hyprland desktop for **Debian 13 (Trixie)** where everything takes its colors from the wallpaper.
Change the wallpaper and the bar, terminal, menus, notifications, lock screen, GTK and Qt apps,
and even `btop`, `cava` and the terminal prompt follow, in about a second, without reloading
anything.

Built on a 14" laptop with a French AZERTY keyboard; it works on any single-screen Debian machine
and in any language.

## What you get

| | |
|---|---|
| **Theme from the wallpaper** | pywal16 palettes, cached per wallpaper so switching is instant. Applied live to Waybar, kitty (and everything open in it), Rofi, SwayNC, GTK 3/4, Qt, hyprlock, Hyprland borders, btop, cava, Papirus folder icons and Discord (pywal-discord). |
| **Wallpaper transitions** | *Outline*: characters are drawn first, then the scene fills in around them (optional AI model, see below). *Classic*: awww wipes and waves. |
| **8 bar styles** | Default, Line, Zen, Experimental, Capsule, Powerline, Dock (hides until you touch the screen edge) and Island (an iOS-style dynamic island at the top). Any edge, three sizes, adjustable gap. |
| **Settings app** (`Super + H`) | Bar, wallpaper transition, lock screen, menus, terminal prompt, display, night light, Wi-Fi, Bluetooth, sound, power, mouse, language and keyboard, default apps, and every keyboard shortcut (rebindable). |
| **Quick panel** (`Super + N`) | Live music card, Wi-Fi, Bluetooth, mute, mic, do-not-disturb, night light, caffeine, screenshot, volume and brightness sliders. |
| **Launcher** (`Super + Q`) | Apps and files in one window; `Tab` switches between them, `Ctrl + Enter` opens a folder. |
| **Lock screen** | Four designs (Classic, Clock, Card, Minimal), picked in Settings. |
| **Power menu** (`Super + Esc`) | Radial or cards, asks again before shutdown, reboot and log out. |
| **Terminal** | kitty with a thin cursor that leaves a short trail, three zsh prompts (`prompt-style blocks / frame / right`), fzf, zoxide, eza, a fastfetch dashboard with usage meters, btop and cava in the wallpaper colors. |
| **Laptop care** | Power profiles, caffeine, night light, dim / lock / suspend on idle, hibernate before the battery runs out. |

## Requirements

- **Debian 13 (Trixie)**, Testing or Sid. Bookworm works with backports, with older Hyprland.
- A user with `sudo`, and an internet connection during the install.
- Intel or AMD graphics. **NVIDIA**: see [NVIDIA](#nvidia) below.

GNOME and GDM stay installed and working: Hyprland is added as another session on the login screen.

## Install

```bash
git clone https://github.com/AKIM-08/akim-dotfiles.git
cd akim-dotfiles
./install.sh
```

Run it as your normal user, not with `sudo`; it asks for your password when it needs it. It takes
a while the first time (it builds `awww` from source). Everything it prints is also saved to
`~/.cache/akim-dotfiles-install.log`.

Then log out, choose **Hyprland** in the login screen's session menu (the gear icon), and log in.
`Super + H` opens Settings, `Super + G` lists every shortcut.

What the installer does:

- Installs the packages (APT, plus `pywal16` and `waypaper` with pipx), the JetBrainsMono Nerd
  Font, the Catppuccin GTK and Kvantum themes and Papirus icons.
- Copies the configs into `~/.config`. **Every folder it replaces is backed up first**
  (`<folder>.backup-before-akim-dotfiles-<date>`), and so is `~/.zshrc`.
- Puts the wallpapers in `wallpapers/` inside **your** Pictures folder: the one your system
  language uses (`~/Pictures`, `~/Images` in French, `~/Bilder` in German...). Screenshots go to
  `<Pictures>/Screenshots`, screen recordings to `<Videos>/Recordings`.
- Registers the Hyprland session and sets up PAM so hyprlock accepts your password.
- Makes zsh your shell with Oh My Zsh.

### Update

```bash
akim-update
```

It pulls the latest version, copies only the files that changed, restarts what needs it (bar,
notifications, desktop widgets) and tells you if Hyprland finds a problem in its config.
`akim-update --check` only says whether an update is waiting; `akim-update --dry-run` lists the
files it would copy. If the command isn't found yet, run it once as
`bash ~/akim-dotfiles/install/update.sh`.

Kitty is installed from its official build when Debian's is too old (Debian 13 has 0.41; the
draggable scrollbar needs 0.43). apt doesn't update that one: `akim-update` does, or run
`kitty-update` on its own. `bash ~/akim-dotfiles/install/kitty-latest.sh --remove` goes back to
Debian's kitty.

When the installer itself changed (new packages), `akim-update` tells you to run it again:

```bash
cd akim-dotfiles
./install.sh
```

Both **keep your choices**: bar theme and position, lock screen, power menu style, wallpaper
transition, night light, pointer size, desktop widgets, shortcuts you changed, and your default
apps.

### Undo

```bash
./install.sh --rollback
```

Puts back the configuration you had before the first install (the oldest backup of each folder).

## Shortcuts

`Super` is the Windows key. Workspaces use the number row: on AZERTY that is
`Super + & é " ' ( - è _ ç à`.

| Keys | Action |
|---|---|
| `Super + Return` | Terminal (kitty) |
| `Super + Q` | Launcher (apps and files) |
| `Super + F` | Files (Nautilus) |
| `Super + B` | Web browser |
| `Super + A` | Close the window |
| `Super + W` | Wallpaper picker |
| `Super + Alt + ←` / `→` | Previous / next wallpaper |
| `Super + N` | Quick panel |
| `Super + Shift + N` | Notifications |
| `Super + H` | Settings |
| `Super + Shift + H` | Quick settings (Rofi) |
| `Super + Shift + T` | Bar style |
| `Super + G` | Shortcut list |
| `Super + V` | Clipboard history |
| `Super + P` | Screenshot menu |
| `Super + Shift + P` / `Super + Alt + P` | Screenshot of a region / the whole screen |
| `Super + Shift + R` | Record the screen |
| `Super + L` | Lock |
| `Super + Esc` | Power menu |
| `Super + T` / `Super + Tab` | Float the window, centered |
| `Super + Shift + F` | Fullscreen |
| `Super + S` / `Super + Shift + S` | Show the scratchpad / send the window to it |
| `Super + C` | Caffeine (stay awake) |
| `Super + F12` | Power profile |
| `Super + M` | Log out of Hyprland |

Change any of them in **Settings → Shortcuts**: click *Change* and press the new keys. Your changes
live in `~/.config/hypr/user-binds.hl` and survive updates.

## Everyday use

**Wallpapers.** Drop images (`.jpg`, `.png`, `.webp`, any name) into `<Pictures>/wallpapers`.
They get a cached palette in the background, so switching to them is instant. Use images at least
as large as your screen.

**Outline transition.** For the transition that draws people and characters first, install the
detection models once:

```bash
~/.config/hypr/scripts/wallfx/wallfx-setup.sh
```

(a few hundred MB in `~/.local/share/wallfx`; `--remove` uninstalls it). Pick *Outline* or *Classic* in
Settings → Appearance → Wallpaper.

**Terminal prompt.** `prompt-style blocks`, `prompt-style frame` or `prompt-style right`, or
Settings → Appearance → Terminal. `fastfetch` shows the system dashboard.

**Language.** Settings → Language & region changes the system language (asks for your password,
applies at the next login) and the keyboard layout (immediately; two layouts switch with
`Alt + Shift`).

**Idle.** By default the screen dims after 10 minutes, locks and turns off after 15, and the
laptop sleeps after 20. Set each time separately on battery and plugged in (or *Never*) in
Settings → Power → When idle. On battery it also hibernates before running empty (needs swap).

**Updating.** `akim-update` updates the dotfiles and kitty; `kitty-update` updates only kitty.
See [Update](#update).

## Customising

Your own changes are safest in these files, which updates never replace:

| File | For |
|---|---|
| `~/.config/hypr/user-settings.hl` | Any Hyprland setting (Settings writes here too) |
| `~/.config/hypr/user-binds.hl` | Your shortcuts |
| `~/.config/hypr/user-apps.hl` | Default terminal and file manager |

Everything else is in the repo:

```
.config/
├── hypr/            Hyprland, hyprlock (4 designs), hypridle, and the scripts:
│   └── scripts/     settings.py, quickpanel.py, island.py, apply-pywal-theme.sh, wallfx/ ...
├── waybar/          bar themes (themes/<name>/), layout.py builds the live config
├── rofi/            launcher and menus
├── kitty/  swaync/  fastfetch/  btop/  wal/ (pywal templates)  gtk-3.0/  gtk-4.0/  qt5ct/  qt6ct/
omz-custom/themes/   the three zsh prompts
wallpapers/          the wallpapers copied on install
install/             debian.sh (packages), common.sh (configs), rollback.sh
```

## NVIDIA

Uncomment these two lines near the top of `~/.config/hypr/hyprland.hl`, then log out and back in:

```
env = LIBVA_DRIVER_NAME,nvidia
env = __GLX_VENDOR_LIBRARY_NAME,nvidia
```

## Troubleshooting

| Problem | Try |
|---|---|
| The install stopped with an error | Read `~/.cache/akim-dotfiles-install.log`, fix the reported step, run `./install.sh` again |
| No bar | `~/.config/waybar/scripts/launch.sh` |
| Colors didn't follow the wallpaper | `~/.config/hypr/scripts/apply-pywal-theme.sh` |
| A red error banner at the top | A line in `~/.config/hypr/user-settings.hl` or `user-binds.hl` is not valid for your Hyprland version |
| Outline transition does nothing | Run `wallfx-setup.sh` (above); the last run is logged in `~/.cache/wallfx/last.log` |
| Bluetooth missing | `sudo systemctl enable --now bluetooth` |
| Language didn't change | Log out and back in; the new language applies at login |

## Credits

Hyprland, Waybar, Rofi, SwayNC, kitty, hyprlock / hypridle, awww, pywal16, waypaper, Catppuccin,
Papirus, Breeze cursors, JetBrainsMono Nerd Font, Oh My Zsh, fastfetch, btop, cava, and the
`isnet` segmentation models used by the outline transition.
