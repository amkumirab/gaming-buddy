# Gaming Buddy v0.1.0 Windows acceptance

- Date: 2026-11-23
- [Public release](https://github.com/amkumirab/gaming-buddy/releases/tag/v0.1.0)
- Source commit: `1e97b4de486485ca0d4b7e4d1c75e30d40f55b2e`
- [Manual build](https://github.com/amkumirab/gaming-buddy/actions/runs/45171972656) and
  [tagged build](https://github.com/amkumirab/gaming-buddy/actions/runs/45180075600)
- Published files: `Gaming-Buddy-Setup-0.1.0-x64.exe` and
  `Gaming-Buddy-Setup-0.1.0-x64.exe.sha256`
- Installer SHA-256: `4fe98d6b76f4165b6ba8edf49dbe175b53d5ad59750c0a73c0cbe0864a491d73`
- Environment: disposable Windows 11 Home x64 VM, build 26300.9457, standard local
  account, no installed Python or developer tools. The manual build's test workspace
  was archived before installing the tagged build with fresh application state.

## Published installer

| Check | Result |
| --- | --- |
| Version agreement, 566 tests, Ruff, PyInstaller, Inno Setup, SHA-256, hosted installer lifecycle | Passed on the tagged build |
| Install, Start menu shortcut, desktop shortcut, Windows uninstall registration | Passed with unattended setup under a standard account |
| Desktop launch, tray menu, dashboard restored from tray, normal exit | Passed |
| Second launch while running | Passed; the second process exited with code 0 and the first remained open |
| Global panel, quick finder, and region capture shortcuts | Passed from the Windows desktop |
| Screenshot and original-resolution viewer | A 266 × 136 lossless PNG was saved and pinned, reopened after restart, and viewed at 100% |
| Markdown note and checklist | Multiline text and a checked task survived exit and restart |
| Reinstall and silent uninstall | The actual SQLite database, captured PNG, and settings were preserved |
| Interactive uninstall | Choosing **No** preserved user data and settings. Program entries, shortcuts, and an enabled Windows sign-in entry were removed |
| Reinstall after uninstall | The saved note and capture reappeared in Quick Finder |
| Public downloads | Both assets downloaded without GitHub authentication. The updater accepted their names and verified the installer checksum |

The manual build also verified the compact panel, focus mode, click-through mode,
pin cycling, and a replacement panel shortcut after restart. Its installer had a
different hash from the final tagged package.

## Updates and publication

The manual build displayed the no-release message before the first Release was
published. An earlier attempt showed a connection error; the cause was not determined.
After publication, the exact released application reported that 0.1.0 was the latest
published version. The newer-version path passed with a simulated release in the test
suite.

The tagged workflow built and tested the package, then failed at draft creation
because the GitHub CLI ran outside a repository checkout without an explicit target.
The draft used the same verified tagged artifact. The
[workflow fix](https://github.com/amkumirab/gaming-buddy/commit/f608c60) specifies the
target repository while preserving the tag-only draft gate.

## Test limits

An older-to-newer upgrade was not applicable to this first public release. The
interactive setup wizard, explicit data purge, Windows 10, physical monitor reconnect,
negative-coordinate display layouts, and real-game behavior were not exercised in
this VM. The installer is unsigned.
