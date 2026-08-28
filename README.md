# Gaming Buddy

<p align="center">
  <img src="src/gaming_buddy/assets/app-icon.png" alt="Gaming Buddy logo" width="180">
</p>

Gaming Buddy is a lightweight Windows overlay for saving notes and pinning cropped
screenshots without leaving a game. This repository contains the first working prototype.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![PySide6](https://img.shields.io/badge/UI-PySide6-41CD52)
![License](https://img.shields.io/badge/license-Proprietary-7c5cff)

![Gaming Buddy MVP](docs/ui-preview.png)

## About the project

Gaming Buddy keeps useful game information visible while you play. It provides a compact
control panel for capturing a clue, saving a short note, and placing movable cards over a
game window. The prototype is designed for quick interaction and stores its data locally.

## Prototype features

- Capture a region at the monitor's native pixel resolution and pin it above the game
- Import PNG, JPEG, BMP, and WebP images by file picker, drag and drop, or clipboard paste
- Preserve imported files at their original quality and skip duplicate image content
- Annotate screenshots with a pen, arrows, rectangles, text, and a pixel-restoring eraser
- Undo, redo, or reset edits and save the result as a new lossless copy
- Create, save, and pin quick text notes
- Move and resize every pinned card
- Open screenshots at full resolution with Fit, 100%, and zoom controls
- Adjust overlay opacity
- Switch pins into click-through mode
- Organize cards by game name
- Search saved cards by title, note text, or game
- Mark important cards as favorites and filter the library
- Edit saved card titles, game names, and note text without recreating them
- Copy note text or full-resolution screenshots directly to the clipboard
- Open a screenshot's local folder from its card menu
- Move deleted cards to a 30-day recycle bin with quick undo and restore controls
- Detect the active Windows game and switch to its linked card profile automatically
- Show only the active game's saved pins, plus General pins, when profiles switch
- Optionally hide pins outside linked games and restore them when gameplay resumes
- Back up cards, screenshots, profiles, and portable settings to a verified ZIP archive
- Restore backups by safely merging cards and skipping exact duplicates
- Restore pinned cards, positions, sizes, and opacity after restarting
- Temporarily show or hide all saved pins without deleting them
- Keep restored pins visible when monitors or resolutions change
- Persist everything locally in SQLite
- Configurable global shortcuts and a system tray menu
- First-run setup guide with a quick overview of capture, pins, and shortcuts
- Optional launch at Windows sign-in without administrator access
- Per-user Windows installer with clean update and uninstall support
- No code injection and no game-memory access

## Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+Shift+G` | Show or hide the control panel |
| `Ctrl+Shift+S` | Capture a screen region |
| `Ctrl+Shift+L` | Toggle click-through mode for all pins |

Choose **Keyboard shortcuts…** in the control panel or tray menu to replace any default.
Changes are saved locally and take effect immediately. Gaming Buddy prevents duplicate,
empty, and modifier-free shortcuts.

## Run from source

Windows 10 version 1809 or newer and Python 3.11 or newer are required.

```powershell
git clone https://github.com/amkumirab/gaming-buddy.git
cd gaming-buddy
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
gaming-buddy
```

You can also run it without installing the command:

```powershell
python -m gaming_buddy
```

## Install on Windows

Download the latest `Gaming-Buddy-Setup-*-x64.exe` file from the repository's
[Releases](https://github.com/amkumirab/gaming-buddy/releases) page and run it. The
installer does not require administrator access. It creates a Start menu shortcut and
can optionally create a desktop shortcut.

Updates reuse the same installation and preserve the local workspace. Uninstalling the
application removes program files, shortcuts, and its launch-at-sign-in entry but keeps
notes and screenshots under `%LOCALAPPDATA%\GamingBuddy`. Interface preferences, shortcuts,
and game profiles remain in the current user's Windows settings.

Unsigned preview builds may show a Windows SmartScreen warning. Every release includes
a `.sha256` file so the installer can be checked before it is run.

## How to use

1. Enter the current game name in the top field.
2. Write a note and choose **Save** or **Pin note**.
3. Choose **Capture area**, drag around a clue or map, and release.
4. Choose **Import image…**, drag image files onto the panel, or paste an image with `Ctrl+V`.
   Select **Save** or **Save and pin** after checking the preview.
5. Right-click an image card or pin and choose **Annotate image…**. Mark it with a pen,
   arrow, rectangle, text, or eraser, then choose **Save copy** or **Save and pin**.
6. Drag pins by their header and resize them from the bottom-right corner.
7. Double-click a pinned image to inspect the lossless original at full resolution.
8. Use **Hide all pins** to clear the screen without losing the saved workspace.
9. Enable **Click-through pins** so mouse input goes to the game.
10. Open **Keyboard shortcuts…** to personalize controls without restarting.
11. Right-click a saved card or pin to edit, copy, or locate its original file.
12. Move a card to **Recently deleted** and use **Undo** immediately if it was accidental.
13. Open a game, return with the panel shortcut, enter its name, and choose
    **Link detected app**. Enable **Auto-switch game profiles** to switch automatically.
14. Enable **Hide pins when a linked game loses focus** to keep overlays off other apps.
    Manual **Hide all pins** remains in effect when you return to the game.
15. Choose **Backup workspace…** to save a portable ZIP. Use **Restore backup…** to inspect
    and merge it without deleting the current library.
16. Open **Getting started…** from the panel or tray whenever you want the quick guide again.
17. Toggle **Launch at Windows sign-in** from the tray to keep global shortcuts ready after
    signing in.

Captured images and the SQLite database are stored under:

```text
%LOCALAPPDATA%\GamingBuddy
```

## Project structure

```text
gaming-buddy/
├── src/gaming_buddy/
│   ├── app.py          # Application entry point
│   ├── dashboard.py    # Main control panel
│   ├── capture.py      # Screen-region capture
│   ├── card_editor.py  # Saved-card editor
│   ├── pin.py          # Movable overlay cards
│   ├── profiles.py     # Active-game detection and profile mappings
│   ├── profile_dialog.py # Profile manager
│   ├── hotkeys.py      # Global keyboard shortcuts
│   ├── image_annotation.py # Non-destructive screenshot annotation tools
│   ├── image_import.py # Lossless image import and duplicate checks
│   ├── pin_visibility.py # Focus-aware pin visibility controller
│   ├── shortcut_dialog.py # Shortcut settings dialog
│   ├── onboarding.py   # First-run setup guide
│   ├── startup.py      # Per-user Windows startup setting
│   ├── trash_dialog.py # Recently deleted cards and permanent cleanup
│   ├── workspace_backup.py # Verified backup and restore
│   └── storage.py      # Local SQLite persistence
├── tests/              # Automated storage and path tests
├── packaging/          # Windows executable and installer configuration
├── scripts/            # Release metadata validation
├── .github/workflows/  # Test and tagged-release automation
└── docs/               # Project preview assets
```

## Privacy and storage

- Notes and captured images remain on the user's computer.
- Deleted cards and their images remain recoverable locally for 30 days unless the recycle
  bin is emptied earlier.
- Interface preferences, shortcut mappings, and profiles use the current Windows account.
- The prototype does not require an account or cloud connection.
- Captures are created only after the user activates the capture shortcut.
- Imported images are copied into the local capture library only after confirmation.
- Screenshot annotations are saved as new local PNG files; the source image is unchanged.
- Active-game detection reads only the foreground window title, process ID, and executable name.
- Automatic profile switching is disabled by default and profile links remain local.
- Focus-aware pin hiding is disabled by default and works only with locally linked games.
- Launch at sign-in is optional and uses the current user's Windows startup entry.
- Backups are written only to the location selected by the user and are never uploaded.
- Backup ZIP files are not encrypted, so they should be stored in a trusted location.
- Saved cards and captured images can be removed by deleting `%LOCALAPPDATA%\GamingBuddy`.

## Compatibility and fair-play note

The MVP uses ordinary top-level Windows windows. It does not inject code, read game
memory, automate input, or bypass anti-cheat software. Borderless-windowed mode gives
the most reliable overlay experience. Some exclusive-fullscreen games may hide normal
desktop overlays. Always follow the rules of the game you are playing.

## Current scope and roadmap

This release intentionally focuses on the core overlay and notebook experience. Planned
improvements include text recognition, spoiler-safe layered hints, optional web lookup,
and better multi-monitor support.

## Development

```powershell
python -m pytest
python -m ruff check .
```

Build the Windows application and installer with:

```powershell
python -m pip install -e ".[dev,packaging]"
python scripts/validate_release.py
python -m PyInstaller --clean --noconfirm packaging/gaming-buddy.spec
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging/gaming-buddy.iss
```

Pushing a tag that exactly matches the project version, such as `v0.1.0`, runs the
Windows release workflow and publishes the installer and its SHA-256 checksum. Running
the workflow manually builds a downloadable test artifact without publishing a release.

## Ownership and license

Copyright © 2026 **Amir Ali Mirab Zadeh Ardekani**. All rights reserved.

This is proprietary software. The source is available for viewing, but copying,
modification, redistribution, commercial use, or creation of derivative works is not
permitted without prior written authorization. See [LICENSE](LICENSE) for the complete
terms.
