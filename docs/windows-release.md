# Windows release verification

## Current distribution status

Version `0.1.0` has no official release yet. Its synchronized version sources are
`pyproject.toml`, `src/gaming_buddy/__init__.py`, `packaging/gaming-buddy.iss`, and
`packaging/version_info.txt`. The first release is pending an interactive test on a
clean Windows machine without Python. A successful Actions build is a test artifact,
not evidence that these desktop checks have passed.

## Build and automated verification

1. Confirm `main` is current and the working tree is clean.
2. Run `windows-release.yml` manually on `main` and record its commit SHA and run URL.
3. Require version validation, tests, Ruff, PyInstaller, Inno Setup, and SHA-256 generation
   to pass. Do not reuse an older run merely because its version number is identical.
4. Require the installer lifecycle step to pass. It verifies the checksum, per-user
   installation and uninstall registration, executable version, Start menu and desktop
   shortcut targets, application startup with the bundled Python DLL, removal of stale
   runtime files during reinstallation, and preservation of workspace files and settings
   during reinstallation and silent uninstall.
5. Download both the Windows installer artifact and the installer-test report. Its JSON
   records the commit, version, checksum, completed checks, and test limitations.

The lifecycle script refuses to run outside a disposable GitHub-hosted Windows runner.
It must not be run against a personal workspace. The runner contains Python, although
the launched app's PATH is restricted to Windows directories and external Python/Qt
environment overrides are removed. Retention checks use the app-created database and
synthetic note/image sentinels. They do not exercise note editing or region selection.

## Clean-machine desktop acceptance

Use a disposable Windows 10 version 1809 or newer / Windows 11 x64 VM or test machine
with no installed Python, developer tools, or previous Gaming Buddy installation. Do not
use another person's computer or saved workspace. Record the Windows version, build
commit, installer SHA-256, and result of each check.

1. Verify the downloaded installer against its checksum file before running it.
2. Install as a standard user. Check Start menu and optional desktop shortcuts, the icon,
   and the entry in Windows Installed apps.
3. Launch from the shortcut. Complete onboarding, open the tray menu, hide the panel,
   and show it again from the tray.
4. Exercise the default global shortcuts: panel, capture, quick finder, click-through,
   focus mode, and pin cycling. Configure a replacement shortcut and restart to verify it.
5. Capture a visible test region. Inspect the PNG at 100%, save it, pin it, restart, and
   reopen the saved original. Do not capture private desktop content.
6. Save a multiline Markdown note, edit it, restart, and verify its complete text and
   preview. Verify pinned-note restoration.
7. Reinstall the same build and verify that cards, screenshots, layouts, shortcuts, and
   settings survive. When a prior official version exists, also test a genuine
   older-to-newer upgrade. Same-version reinstallation is not a version upgrade.
8. Uninstall interactively, choose **No** when asked to remove data, and verify that
   program files, shortcuts, uninstall registration, and sign-in entry are removed while
   workspace and settings remain. Reinstall and reopen the note and screenshot.
9. Test silent uninstall on the disposable profile: data must remain by default.
   Test `/PURGEUSERDATA` only on disposable fixtures if explicit data removal is required.

An unavailable clean machine means these checks remain pending. Do not claim that a
restricted PATH on a development machine or runner is a clean-machine test.

## Official publication

After acceptance passes, ensure the intended release commit is still `main`, validate
`--tag v0.1.0`, and push an annotated tag `v0.1.0` at that exact commit. Preserve the
workflow's tag-only publish condition. The tagged workflow rebuilds and retests the
commit, verifies the exact checksum and asset names, and creates a draft release.
Repeat desktop acceptance against that exact tagged installer before publishing the
draft with `gh release edit v0.1.0 --draft=false --latest`. A rebuilt installer may have
different bytes even at the same commit, so a development-build check alone must not
silently approve the new tagged output.

Expected assets:

- `Gaming-Buddy-Setup-0.1.0-x64.exe`
- `Gaming-Buddy-Setup-0.1.0-x64.exe.sha256`

Download both through the public release asset links without authentication. Check:

```powershell
$installer = 'Gaming-Buddy-Setup-0.1.0-x64.exe'
$expected = ((Get-Content -LiteralPath "$installer.sha256" -Raw).Trim() -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
if ($actual -ine $expected) { throw 'Installer SHA-256 mismatch.' }
```

`updates.py` requires these exact names for the version in the release tag. Confirm
`fetch_latest_release()` parses the public release and `download_release()` accepts its
checksum. Equal versions must report up to date; newer versions must report an update;
an absent release (HTTP 404) must report that no release is published. Tests cover all
three controller outcomes without publishing a fabricated newer version.

Update README with the actual release URL and tested installation result only after the
public asset download succeeds. Keep untested compatibility or upgrade cases explicit.
If acceptance fails, hold publication and fix the build; do not move an already public
tag or silently replace its installer with different bytes.
