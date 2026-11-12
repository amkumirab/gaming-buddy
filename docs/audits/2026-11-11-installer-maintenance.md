# Installer maintenance: local verification

Local verification date: 2026-11-11. Application version remains 0.1.0.
This report records the original local checks. Delivery verification was authorized
on 2026-11-12; subsequent results and build identity are recorded separately below.

## Implemented behavior

- Ready-page operation and version summary distinguish installation, upgrade and
  same-version reinstall. Previous directory and shortcut choices remain in use.
- Numeric version checks inspect registration in both registry views and the existing
  executable. The highest verified value protects against stale metadata. Unknown or
  unreadable versions and downgrades stop before program-file replacement.
- Setup/application mutexes prevent concurrent setup and cooperative app startup. The
  app holds its mutex until process termination, including Qt and storage teardown.
- Running-app messages ask the user to Quit from the tray. Silent setup/uninstall also
  refuses a running application; the installer does not force-close it.
- Preflight rechecks versions and app state and probes existing files with OPEN_EXISTING
  write access without modifying them. Locked/inaccessible files and runtime reparse
  points are rejected before stale runtime cleanup.
- Optional post-install launch waits up to 15 seconds for Setup to finish. Manual startup
  still refuses an active installer before opening the workspace. Waiting never bypasses
  the check; timeout and failure close any newly acquired guard handle.

The existing QLockFile/local-socket single-instance protocol, app identity, per-user
installation paths, licensing, update checks and data-retention defaults are preserved.
No new dependency or background worker is required. No remote workflow was dispatched
during the original local implementation on 2026-11-11.

## Completed checks

| Check | Result | Scope |
| --- | --- | --- |
| Full suite, Python 3.11.9 | 565 passed in 146.50 seconds; exit 0 | Native Windows Qt platform, PySide6 6.12.0 |
| Full suite, Python 3.12.10 | 565 passed in 145.27 seconds; exit 0 | Native Windows Qt platform, PySide6 6.12.0 |
| Ruff | Passed | Entire repository |
| Version validation | Passed | Existing metadata sources remain synchronized at 0.1.0 |
| Fresh PyInstaller build | Passed | New installer guard included in module analysis |
| Inno Setup compilation | Passed | Inno Setup 6.7.3; final compile 48.125 seconds |
| SHA-256 generation and readback | Passed | Computed hash matches sidecar |
| First install, upgrade, reinstall and uninstall | Passed | Actual compiled fixture installers and native operations |
| Downgrade protection | Passed | 0.1.0 to 0.0.9 and 1.10.0 to 1.9.0 refused; installed program bytes unchanged |
| Invalid/stale registration | Passed | Malformed versions, extra version components, newer registry value, stale lower registry value, other registry view |
| Running app and locked legacy file | Passed | Refusal before program bytes change; successful retry after closing/unlocking |
| Mutex lifetime and post-install handoff | Passed | Real Windows subprocesses; normal startup refusal, bounded timeout, and delayed real-main workspace entry |

The native installer fixtures compile the production maintenance code with unique test
GUIDs, mutexes, registry keys, paths and small .NET versioned executables. They never
install or remove the actual Gaming Buddy application identity. The helper asserts
identity/path substitutions before compilation. All dialogs are suppressed during
these native tests, and cleanup removes the fixture's uninstall registration.

The retention fixture contains real SQLite multiline notes, checklist text, revealed
hint content, tags/favorite/pin geometry/lock state, an image reference with PNG bytes,
an INI preference, and a fixture registry setting. Database and image/settings bytes
remain unchanged across upgrade, reinstall and uninstall, and stored cards are reopened.
This is stronger than checking an empty database or text-only retention sentinel, but
does not establish installed real-app GUI interaction or a genuine historical migration.

An early test exposed a fixture cleanup race after uninstall; cleanup was made
idempotent. A failing post-install test also reproduced the missing wait behavior
before the bounded handoff was implemented. No assertion was weakened or test removed.

## Local artifact

- Installer: `release/Gaming-Buddy-Setup-0.1.0-x64.exe`
- Size: `36158142` bytes
- Sidecar: `release/Gaming-Buddy-Setup-0.1.0-x64.exe.sha256`
- SHA-256: `59d0c4ab20c94b6c0f8163830d5292518569589aa46ad220cd1c2b7c66508eb3`
- Detailed build output: `build/installer-maintenance-qa/build-final.log` (local only)
- Fixture logs: `build/installer-maintenance-qa/full311-final` and `full312-final` (local only)

## Limits and delivery status

The real application's installer was built but not installed over the user's workspace.
Clean Windows without Python, interactive Ready-page visual acceptance, actual installed
app tray/hotkey/capture/editing/shutdown, and a genuine older-official-version upgrade
remain untested. Fixture versions are not historical Gaming Buddy releases. New checks
do not alter previously downloaded installers. Interrupted installation does not have
transactional rollback of every program file; rerunning a suitable installer remains
the recovery path while retained user data stays outside the program directory.

The original implementation was kept local until delivery was authorized on 2026-11-12.
See [the user guide](../installer-maintenance.md) and
[specification with primary sources](../specs/installer-maintenance.md).

## Delivery verification: 2026-11-12

The runtime and test files matched the hashes recorded after the original local build.
Both full native Windows suites were rerun without skipped tests: Python 3.12 passed
565 tests in 148.23 seconds, and Python 3.11 passed 565 tests in 140.50 seconds. Both
processes exited with code zero. Ruff and version validation also passed again.

The changes were organized into independently verifiable increments. Tests run against
separate snapshots of the staged index passed: 11 startup/packaging checks, 8 native
version/data-retention cases, and 2 native running-app/locked-file cases. These checks
supplement the complete suites rather than replacing them. No assertion or quality
threshold was weakened to accommodate the split.

The initial delivery test invocation lacked the parent of its chosen temporary directory.
The directory was created and the unchanged full suites were rerun successfully; this
was a test-invocation setup error, not a passing result or an application regression.

Remote [CI](https://github.com/amkumirab/gaming-buddy/actions/runs/43157560556) passed
565 tests and Ruff in both Python jobs. The [fresh build](https://github.com/amkumirab/gaming-buddy/actions/runs/43157738261)
also passed, including its separate production-installer lifecycle job. The downloaded
installer, sidecar and acceptance report matched. Exact identity, checksum and test
boundaries are recorded in the [November 12 candidate](../release-candidates/2026-11-12.md).
No official Release, version tag or automatic future delivery schedule is part of this change.
