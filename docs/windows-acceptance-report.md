# Windows installer acceptance report template

This blank template is not test evidence. Copy it for an actual test session. Use
**Pass**, **Fail**, **Not tested**, or **Not applicable** with an explanation. Never
carry a pass forward to a rebuilt installer with a different SHA-256.

## Installer and environment

- Tester and test date: Not recorded
- Build run URL and full commit SHA: Not recorded
- Version and installer filename: Not recorded
- Installer SHA-256 and matching checksum file: Not recorded
- Windows edition, version, build, and architecture: Not recorded
- Disposable VM or test-machine description: Not recorded
- Standard-user account used: Not recorded
- Python and developer tools absent before installation: Not verified
- No previous Gaming Buddy installation or workspace: Not verified
- License shown by this installer permits the planned evaluation: Not verified

## Results

Follow [Windows release verification](windows-release.md#clean-machine-desktop-acceptance).
Use synthetic notes and screenshots. Do not attach private desktop content or data.

| Check | Result | Evidence or failure details |
| --- | --- | --- |
| Downloaded installer matches its SHA-256 file | Not tested | |
| Install as standard user without Python | Not tested | |
| Start menu, optional desktop shortcut, icon, Installed apps entry | Not tested | |
| Launch, onboarding, tray menu, hide and restore panel | Not tested | |
| Default global shortcuts and replacement shortcut after restart | Not tested | |
| Region screenshot saved, pinned, inspected at 100%, reopened after restart | Not tested | |
| Multiline Markdown note saved, edited, reopened with full content | Not tested | |
| Pinned checklist toggled and state retained after restart | Not tested | |
| Same-build reinstall preserves cards, captures, layouts, shortcuts, settings | Not tested | |
| Older official version upgraded with representative data preserved | Not tested | Record both versions; use Not applicable for the first official release. |
| Interactive uninstall with No preserves data and removes program registration | Not tested | Include shortcuts and launch-at-sign-in entry. |
| Reinstall after uninstall reopens saved note and screenshot | Not tested | |
| Silent uninstall preserves workspace and settings by default | Not tested | |
| Explicit purge removes only the disposable test workspace and settings | Not tested | Optional destructive test on fixtures only. |

## Publication decision

- Blocking failures or untested required checks: Not assessed
- Exact tagged installer retested, if different from the development build: Not tested
- Public installer and checksum downloaded without authentication: Not tested
- Update checker: absent, equal, and newer release outcomes: Not tested
- Decision: **Pending; this template does not approve publication.**

A successful automated build, a restricted PATH, or a developer-machine smoke test
does not establish clean-Windows acceptance. Keep the release as a draft until the
required desktop checks pass for its exact installer bytes. Record any genuine upgrade
case that is unavailable for the first release as Not applicable, not Pass.
