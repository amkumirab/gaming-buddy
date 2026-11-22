# Gaming Buddy 0.1.0 — Windows host verification

Tested on November 21, 2026, using Windows 11 Home 26H2 x64
(build 26300.9974), a standard account, and one 1920 × 1080 display.
Python 3.12.10 was installed on the host. Existing Gaming Buddy files and
settings were kept separate from the disposable workspace during testing.
Their file hashes and exported registry settings matched after restoration.

## Builds under test

- Source: `39b2cbb7e0e72d844ff05f4981ad77f4d770bf05`.
- [Windows installer build and lifecycle check](https://github.com/amkumirab/gaming-buddy/actions/runs/43691672094).
- Installer: `Gaming-Buddy-Setup-0.1.0-x64.exe`.
- Checksum file: `Gaming-Buddy-Setup-0.1.0-x64.exe.sha256`.
- Verified installer SHA-256:
  `ddba08250f087de63ea573074c43a14662e6e0400fce4db676a7f2ed5a797d37`.
- The desktop session used a separate PyInstaller build from the same source
  commit. Its `GamingBuddy.exe` SHA-256 was
  `c5c1d529a4de9c88e47fbe6b4256e771755c281d8b2214f067558f11078844ab`.

## Automated results

| Check | Result | Evidence |
| --- | --- | --- |
| Full test suite, native Windows Qt backend, Python 3.12.10 | Pass | 565 passed in 144.30 seconds. The process exited with code 0 and emitted no fatal exception. |
| Python 3.11 and 3.12 CI | Pass | Both jobs passed on the same source commit in the [Windows test matrix](https://github.com/amkumirab/gaming-buddy/actions/runs/43571466728). |
| Release metadata and Ruff | Pass | `scripts/validate_release.py --tag v0.1.0` and `python -m ruff check .`. |
| PyInstaller and Inno Setup | Pass | Fresh standalone PyInstaller build on the host. The installer build, its checksum, and the separate lifecycle job passed in CI. |
| Installer maintenance fixtures | Pass | The native suite ran all 10 maintenance tests against synthetic packages. Coverage includes version handling, the running-app guard and data retention. |
| Update checker | Pass | Focused tests covered missing, equal and newer releases, asset names and checksum handling. An anonymous live check returned the expected no-release message. No public download was available. |

An exploratory run with `QT_QPA_PLATFORM=offscreen` reported one quick-panel
failure and then stalled. The test process was stopped. The native Windows
rerun completed the whole suite, including the quick-panel and single-instance
tests. The offscreen behavior remains unverified beyond that attempt.

## Standalone desktop results

| Check | Result | Evidence |
| --- | --- | --- |
| Launch and bundled runtime | Pass | The standalone build ran on the desktop with external Python and Qt paths excluded and loaded its bundled `python312.dll`. |
| Installer/startup guard | Pass | With Setup open, the executable displayed the expected guard message and exited with code 1. After Setup closed, the app launched normally. |
| Onboarding and Quick Panel | Pass | All four walkthrough steps completed and the completed state returned after relaunch. |
| Single instance | Pass | The second executable invocation exited with code 0 and restored the original dashboard. |
| Markdown note | Pass | Saved and pinned a six-line note with blank lines and two checklist items, edited the title, and verified that the full content persisted after relaunch. |
| Region capture and library preview | Pass | A fictional clue was captured and pinned as a 276 × 135 PNG. The library displayed its dimensions. The file hash, pin state and card record matched before and after relaunch. |
| OCR of the captured clue | Pass for recognition | The Windows recognition helper returned `NORTH DOOR Access code: 0451`. Saving OCR through the installed app was not verified. |
| Restart | Pass for persistence | A new process reopened the workspace after the test process was stopped. Normal tray exit on this desktop was not verified. |
| Install wizard | Reached license page | Setup was cancelled before installation in this session. The unattended installation below used the same installer. |

## Exact installer tested on the same host

| Check | Result | Evidence |
| --- | --- | --- |
| Unattended install as a standard user | Pass | Setup exited with code 0. Its log recorded no administrative privileges and no restart required. The program, per-user registration, Start and desktop shortcuts, and display icon matched version 0.1.0. |
| Launch from the Start shortcut | Pass | The installed app loaded its bundled `python312.dll` with external Python and Qt paths excluded. |
| OCR in the installed app | Pass | The review dialog recognized `NORTH DOOR Access code: 0451` and saved it to the image card. The trial PATH initially omitted Windows PowerShell. The rerun retained system PowerShell and still excluded external Python. |
| Reinstall the same build | Pass | Removed a deliberately stale runtime file. The database, capture, and exported settings matched the pre-reinstall hashes. |
| Interactive uninstall with **No** at the data prompt | Pass | The log recorded **No** and successful uninstall. The program, shortcuts, registration and a temporary launch-at-sign-in entry were gone. Workspace files and settings matched their baseline. |
| Reinstall after uninstall | Pass | The installed application reopened the sample note and capture. The capture dimensions, PNG hash, pin records, and saved OCR text were verified. |
| Hide and restore | Pass | The dashboard disappeared when closed. A second invocation exited with code 0. The window returned under the original process without creating a second instance. |
| Silent uninstall | Pass | The program and registration disappeared after the uninstaller's final cleanup. The workspace and settings hashes still matched. |
| Upgrade from a prior official release | Not applicable | There is no earlier official release. |
| Interactive install wizard through Finish | Not tested | The actual package was installed in unattended mode. |

## Additional native Qt checks

- The Windows notification area was available and the app registered a visible tray
  icon in a source-process test. Its **Show Gaming Buddy** action restored the
  window and its **Quit** action ended the app process with code 0. The physical
  Windows notification-area click on the installed executable was not verified.
- A replacement shortcut was saved through the settings dialog and read back
  from disk. Physical key presses and global delivery remain unverified.
- The pinned checklist updated to **1 of 2 completed** and retained the check mark
  and count when reopened from SQLite in a new dashboard. The 100% viewer
  control restored the original 276 × 135 pixmap after zooming. These were
  native Qt widget checks from the same source commit.
- The monitor geometry tests passed for simulated negative origins and
  disconnects. A second physical monitor and live reconnect were unavailable.
  Real-game overlay compatibility and performance were not tested.

The display probes used process-local Qt scaling on the 1920 × 1080 monitor.
They measured the full initial frame, including the title bar, against the
available logical desktop. Values are logical pixels.

| Scale | Available area | Panel frame | Result |
| --- | --- | --- | --- |
| 100% | 1920 × 1080 | 830 × 931 | Fits |
| 125% | 1536 × 864 | 830 × 874 | Frame exceeds available height by 10 px |
| 150% | 1280 × 720 | 830 × 728 | Frame exceeds available height by 8 px |
| 200% | 960 × 540 | 830 × 576 | Frame exceeds available height by 36 px |

At 200%, the panel's 560 px minimum client height already exceeds the 540 px
available height. The source suite's 640 px workspace check also failed at
that scale because the native window was constrained to 560 px. This
application sizing issue was reproduced on this build.

On November 22, the [dashboard geometry fix](https://github.com/amkumirab/gaming-buddy/commit/3635fdf318a2c979bc6e7f5b98cad396f857003c)
was verified on the same Windows host. The frame fit at all four scales, with
heights of 931, 864, 720, and 540 logical pixels respectively. The native suite
passed all 566 tests with exit code 0.

This report records host verification. Clean-Windows installation without
Python and the acceptance of the exact tagged installer remain pending.
See [Windows release verification](windows-release.md) for the publication gate.
