# Production readiness and user experience audit

Date: 2026-11-04. Version: 0.1.0. Baseline commit:
`fb70c6aca9985a16f7918a92694ee5d2d1708de6`.

The working tree was clean at the start. This audit preserves the application,
dependencies, licensing model and release workflow. Verification was completed locally
before a separate delivery request authorized pushing the changes. No tag, release or
GitHub setting was created or changed by this audit.

## Architecture and feature inventory

| Area | Current implementation | Assessment |
| --- | --- | --- |
| Startup | `__main__.py` / `app.main`, one QApplication, Qt DPI policy, per-user directories, SQLite, QLockFile and local-socket activation | Implemented; real subprocess startup/second-launch/exit tests exist |
| Main interface | Dashboard coordinates three tabs, tray, settings and existing tools; dedicated Quick Panel, walkthrough and capture-text controllers | Implemented; Dashboard remains a large maintenance concentration |
| Notes | Markdown editing/preview, pinned checklists, shared autosaved draft with fsync and atomic replacement | Implemented; keep existing storage and formatting paths |
| Capture | QScreen snapshots, logical desktop geometry with native-pixel images, mixed-scale crop composition, area/full-monitor actions, delay and review | Implemented; incomplete snapshots needed validation |
| Text extraction | Local Windows OCR through PowerShell/WinRT, background Qt worker, installed languages, image/text review and explicit save | Implemented; no new recognition service needed |
| Overlays | Owned viewers and frameless pins, lock/collapse/resize/snap/opacity/click-through, focus mode and pin cycling | Implemented; collapsed restoration had a position defect |
| Organization | SQLite cards/tags/trash, profile linking and active-executable detection, per-game named layouts, library filters/sorting and Quick Finder | Implemented; no game-memory access or automated game input |
| Portability | Original-image import, annotations, selected-card ZIP export/import, backup merge and duplicate detection | Implemented with bounded-input and atomic batch tests |
| Shortcuts | pynput hook thread emits Qt signals; internal binding validation, collision-safe upgrades and shutdown draining | Implemented; conflicts with other apps/anti-cheat require real Windows/game acceptance |
| Updates | GitHub release metadata, version comparison, bounded installer download and SHA-256 verification | Implemented; absent/equal/newer-release tests already exist |
| Distribution | PyInstaller bundle, Inno Setup per-user installer/uninstaller, synchronized metadata, separate fresh-runner lifecycle job and tag-only draft publication | Implemented; no tag or public Release existed when checked |
| Planned work | Spoiler-safe hints and optional web lookup remain roadmap items | Not implemented or added by this audit |

Existing tests and source were reviewed across storage, capture, pins, settings,
hotkeys, shutdown, backups/imports, updates and packaging. No already-working feature
was recreated and no major architecture change was made.

## Confirmed issues and fixes

| Priority | Reproduction and user impact | Change and regression evidence |
| --- | --- | --- |
| P1: partial card edit | A real SQLite trigger rejects a tag after the card UPDATE and old tags' DELETE. The failed operation leaves new text/title/game and empty tags in the open transaction; an unrelated commit can persist them. | `CardStore.update_details` now commits or rolls back the whole edit. The test checks original values/tags immediately, after another write, and after reopening the database. |
| P2: failed editor save loses the editing surface | The same database failure escapes `_edit_card` after the modal editor has accepted. The user cannot retry using the fields just entered. | Reuse the same editor after a recoverable write error, preserving fields for retry/copy/cancel. Real Qt dialog tests exercise failure then success and failure then cancel. Finished dialogs are explicitly released. |
| P2: incomplete region capture | A monitor returns a null framebuffer. The old virtual-desktop code accepts it and can compose transparent/missing image regions instead of reporting capture failure. | Validate all captured monitor images and logical geometries before creating a painter. Reuse `grab_monitor` validation. Tests inject a failed/removed screen and retain fractional-DPI/negative-coordinate pixel checks. |
| P2: collapsed pin moves on restart | A 48px header saved at y=960 on a 1040px work area is restored at y=780 because its saved expanded height of 260px is used for placement. The same 180px jump occurs with negative coordinates. | Fit the collapsed header's visible height while retaining its expanded height. Tests cover bottom-edge and negative-coordinate placement, expansion bounds and lock retention. |
| P2: short workspace cannot fit panel | Resizing the full panel to 640 logical pixels produces a 730px window because of its explicit minimum. | Reduce the window and library-list minimum heights. Native themed tests and screenshots verify all three tabs at 430x640 with the preview dock hidden. Default initial sizing remains unchanged. |

Affected runtime files are `storage.py`, `capture.py`, `pin.py` and `dashboard.py`.
New regression files are `test_card_update_transaction.py`, `test_card_editor_recovery.py`,
`test_capture_failure.py`, and `test_collapsed_pin_restore.py`; the accessibility suite
also exercises the shorter workspace. No tests were removed or skipped.

## Display reliability: evidence boundaries

The existing capture scale composition and restored-pin geometry support negative
desktop coordinates and mixed logical/native sizes. Those implementations and tests
were retained. The new crop regression uses a 1.25 scale and negative coordinates.

Qt already provides screen-removal fallback. The absence of a custom screen-removal
handler is not proof of a broken physical hot-plug path, so this audit did not add one
or claim that physical disconnection was reproduced. Monitor disconnect/reconnect,
resolution changes while capturing and mixed physical DPI still need the acceptance
matrix below. References:
[QGuiApplication.screenRemoved](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QGuiApplication.html),
[QScreen geometry and DPI](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QScreen.html).

## Resource and visual checks

The actual source application was rendered with its stylesheet and synthetic cards
in a disposable INI/SQLite workspace. `docs/ui-preview.png` was refreshed from that
running interface. It is not a game screenshot or proof of installed-app acceptance.
All three tabs were also inspected at 430x640 with scrolling/navigation available.
The development machine reported one monitor, a 1536x960 logical work area and a Qt
device-pixel ratio of 1.25. This is one observed configuration, not a mixed-DPI matrix.

A short source-process probe warmed up three times, then opened/closed the text review,
original-image viewer and card editor 20 times. Native top-level widget count stayed
at 8. Working set moved from 114446336 to 114753536 bytes; private bytes moved from
69885952 to 70152192. This limited sample does not establish long-duration leak freedom,
game FPS/frame-time impact or a native-allocation profile. No speculative performance
optimization or database/search rewrite was introduced.

Local probe receipts and screenshots are under the ignored
`build/production-readiness-2026-11-04/` directory.

## Validation and release readiness

Baseline: Python 3.12, **514 passed in 81.65s**, process exit zero; Ruff passed.
Final source verification: **523 tests passed** on Python 3.12.10 in 76.99s and
Python 3.11.9 in 73.17s. Both complete processes exited zero; Ruff and release metadata
validation passed. Version remains 0.1.0 in all four metadata files. Existing real-app
subprocess tests cover second launch, normal exit, busy update/recognition shutdown,
walkthrough restart and Capture text. Nine regressions were added for this audit.

The standard isolated wheel build succeeded (890515 bytes), SHA-256:
`e55280fdeb95f5e9e36868f25e1cdbdc6794ec51703775baba44db3174d8f932`.
These source tests use controlled services and synthetic fixtures; they do not prove
that an installed app can capture inside a particular game.

Packaging review confirmed the per-user/no-admin installation, bundled runtime,
version synchronization, predictable installer/checksum names, data-preserving silent
uninstall and explicit destructive purge. The fresh installer-runner refusal guards
and tag-only publication condition remain intact. The existing Actions run
[41782550232](https://github.com/amkumirab/gaming-buddy/actions/runs/41782550232)
validated the baseline binary, not these audit fixes.

Fresh local build identity, file paths and hashes are recorded in the ignored
`build/production-readiness-2026-11-04/artifacts.json` after packaging. A successful
build must not be treated as an installed-app, upgrade or clean-machine test.

## Manual Windows acceptance and next steps

Use the existing [installer acceptance report](../windows-acceptance-report.md) and
[game compatibility/performance report](../game-compatibility-report.md) for the exact
installer bytes. New rows cover compact-pin restoration and short/mixed-DPI workspaces.

- Clean disposable Windows without Python: download/hash check, standard-user install,
  shortcuts, Installed apps entry, launch, walkthrough and tray behavior.
- Default/custom shortcuts, full and compact panels, real region/full-monitor capture,
  Capture text, multiline notes, checklists, restart and content recovery.
- Physical displays at 100%, 125%, 150% and 200%, including a monitor left/above primary;
  collapsed/locked/click-through pins, changed work area, unplug/reconnect and active
  capture cancellation/retry. Confirm all windows remain reachable.
- Representative borderless/windowed and exclusive-fullscreen games. Record real
  behavior; tests with fake screen rectangles and synthetic cards are not game evidence.
- Same-build reinstall, genuine older-to-newer upgrade when available, uninstall with
  No, silent uninstall and reinstall. Check cards, images, profiles, shortcuts and
  layouts. Perform purge only on an explicitly disposable workspace.
- Rebuilt/tagged exact-byte acceptance, public Release download and updater smoke check
  before approving the first official release. Do not publish an older Actions artifact
  as the current version.

No ready clean-Windows environment or real-game test session was available for this
audit. No install/uninstall or purge was run against the user's real profile. These
checks, screen-reader acceptance and long-duration/game resource measurements remain
open. Dashboard decomposition should continue only around work being changed; this
audit did not establish a need for FTS5, a new capture backend or a broad rewrite.
