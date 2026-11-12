# Installer maintenance

## Scope

Keep Inno Setup, the application identity, per-user installation, current version and
data locations. Add explicit Install/Upgrade/Reinstall status, numeric downgrade
protection, and cooperative installation/startup exclusion. Never force-kill the app.
Unknown installed version metadata fails closed before files are changed. Read both
registry views and the target executable; the highest verified version wins.

Use named session mutexes shared by Setup and the application. Keep the application's
mutex until process termination, including shutdown/storage cleanup. Refuse application
startup while Setup is active. Recheck before installation and check writable access to
existing executable/runtime files without modifying them, covering older binaries that
do not yet expose the application mutex. Do not follow runtime directory reparse points.
The optional post-install launch uses a bounded wait (15 seconds) for the Setup mutex
to disappear. This path never bypasses startup exclusion or opens the workspace early.

## Verification

- Native Windows subprocess tests for real mutex lifetime and startup exclusion.
- Compile the actual maintenance script into isolated fixture installers with unique
  application IDs, registry keys, mutexes and paths. No production identity is installed
  or removed on the developer's profile. Fixture payloads are clearly labelled.
- First installation, same-version reinstall, cross-version upgrade, downgrade refusal,
  mismatched/malformed version metadata, running app and locked file refusal, and
  uninstall retention of representative SQLite cards/captures/settings.
- Full Python 3.11/3.12 suites, Ruff, synchronized metadata, fresh PyInstaller/Inno build.
- Installed real-application interaction and clean Windows without Python require a
  separate disposable desktop; do not claim fixture results as those outcomes.

## Primary references

- https://jrsoftware.org/ishelp/topic_setup_appmutex.htm
- https://jrsoftware.org/ishelp/topic_setup_setupmutex.htm
- https://jrsoftware.org/ishelp/topic_scriptevents.htm
- https://jrsoftware.org/ishelp/topic_isxfunc_strtoversion.htm
- https://jrsoftware.org/ishelp/topic_isxfunc_comparepackedversion.htm
- https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw
