# Graceful application shutdown

## Accepted scope

Quit must keep the Qt event loop and storage alive until update workers and screenshot
text recognition have stopped. No forced thread termination or synchronous GUI wait is
allowed. Block new work, cancel update downloads cooperatively, and discard pending
capture requests. Preserve the quick-note draft and pin layout before the final quit.

## Contracts and decisions

- UpdateController and TextRecognitionDialog expose begin_shutdown(), cancel_shutdown(),
  and shutdown_ready. Readiness means the actual thread has ended, not just a UI flag.
- A small ShutdownController owns nonblocking polling, a 60-second deadline, idempotent
  exit, and cancellation. Timeout cancels exit rather than terminating a live worker.
- Show an English "Finishing tasks…" progress dialog with a "Stay open" action while
  workers finish. Restore normal admissions and shortcuts if exit is cancelled.
- Stop owned capture/startup timers and prevent late update dialogs or installer prompts
  during shutdown. Do not automatically commit unreviewed recognition text to a card.
- Keep the existing version, data format, installer, and release workflow unchanged.

## Ordered slices

1. Add independently failing worker lifecycle tests, implement update and recognition
   readiness/admission contracts, and verify the focused tests.
2. Add failing shutdown coordination/dashboard tests, implement deadline and UI flow,
   and verify capture cancellation, late callbacks, saved draft, and pin geometry.
3. Extend subprocess application lifecycle coverage for busy exit, update README, run
   the full suite on Python 3.11 and 3.12, Ruff, release metadata validation, and wheel build.

## Source receipts

- https://doc.qt.io/qt-6/qthread.html#isFinished : finished can precede native cleanup;
  use wait(0) to check completion without blocking the GUI.
- https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html : owned timers support stop()
  and event-driven polling while the GUI remains responsive.

## Delivery limits

Work stays uncommitted until explicitly requested. Tests use disposable data and stub
external networking/recognition at the backend boundary. Installer and clean-machine
manual tests are outside this change and must not be claimed as verified.

## Local verification (2026-10-14)

- Python 3.11 and 3.12: 273 tests passed with process exit zero, both native Windows
  and offscreen. The original 238 tests remain, with 35 additional regression cases.
- Real app subprocesses cover update checking, cooperative download cancellation,
  and recognition during Quit; each verifies a responsive event loop and saved draft.
- Ruff, synchronized version metadata, and wheel packaging passed.
- Independent review findings for timer resumption and late recognition admission
  were reproduced with failing tests and corrected.
- No installer was launched in tests and no real external network/recognition backend
  was used in lifecycle probes. These local checks preceded commit and CI verification.

## Commit verification (2026-10-15)

- Exported staged snapshots isolate each commit from later working-tree changes.
- Worker lifecycle snapshot: 252 tests passed on Python 3.12, offscreen, exit zero.
- Exit coordination snapshot: 270 tests passed on Python 3.12, offscreen, exit zero.
- Application lifecycle snapshot: all 273 tests passed on Python 3.11 and 3.12 with
  native Windows Qt, exit zero. Ruff and release metadata validation also passed.
- Desktop installer acceptance remains untested; this change does not publish a release.

# Persistent library sorting (2026-10-20)

## Accepted scope and success criteria

Add Default, Newest first, Oldest first, and Title A–Z beside library search.
Default preserves pinned/favorite/last-change ordering. Date choices use creation
time, not layout or note modification time. Equal keys use a deterministic card-ID
tie-breaker. Title sorting uses SQLite NOCASE, not locale-specific collation.
Persist the choice in local QSettings; unknown saved values fall back to Default.
Sorting must preserve current and multi-selected cards, preview, and all filters.
Do not change quick-finder ranking, pin cycling, data schema, dependencies, or version.

## Ordered implementation slices

1. Add an optional keyword-only sort contract to CardStore.list, backed by fixed SQL
   order clauses. Prove ordering, filter combinations, stable ties, and invalid input
   with pytest before wiring the UI.
2. Add an accessible labeled QComboBox next to search, restore the persisted choice
   before the first refresh, and reuse refresh_cards selection/preview preservation.
   Test change/reopen, filters, keyboard access, empty lists, and narrow layout.
3. Update README and record verification: full suites on Python 3.11/3.12 with
   process exit zero, Ruff, release metadata validation, and wheel packaging.

## Commands and boundaries

- Test: `.venv/Scripts/python.exe -X faulthandler -m pytest`.
- Lint: `.venv/Scripts/python.exe -m ruff check .`.
- Metadata: `.venv/Scripts/python.exe scripts/validate_release.py`.
- Package: `.venv/Scripts/python.exe -m pip wheel --no-deps --wheel-dir build/verification-wheels .`.
- Match existing Python type hints, StrEnum values, Qt labels, and isolated pytest data.
- Keep SQL ordering allowlisted; never interpolate settings or labels into SQL.
- No unrelated refactoring, test suppression, installer publication, or data migration.
- Build and verify locally; commit/push requires the user's delivery request.

## Source receipts

- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QComboBox.html : item data and
  currentIndexChanged keep stored sort keys independent of visible labels.
- https://doc.qt.io/qt-6/qitemselectionmodel.html#SelectionFlag-enum : NoUpdate
  can restore the current item without selecting an extra card.

## Sorting verification (2026-10-20)

- Baseline: 273 tests passed on Python 3.12, exit zero.
- RED: new storage and dashboard tests failed on the missing sort keyword and control.
- Focused checks: 36 storage tests and 16 sorting/bulk/accessibility tests passed.
- Final serial native Windows runs: 308 tests passed on Python 3.12 (28.85s) and
  Python 3.11 (27.33s), both process exit zero. The original 273 tests remain enabled.
- An initial concurrent native run had two focus-dependent keyboard failures. Both
  groups passed serially (26 tests), then both full suites passed serially. Native
  GUI tests should not compete for the same desktop focus across local processes.
- Ruff and version synchronization checks passed; version remains 0.1.0. The wheel
  built successfully with the standard isolated setuptools build environment.
- Reviewed native Qt screenshots at 470x730 without preview and 1000x730 with preview.
  Offscreen rendering lacked system fonts; native Windows rendering used Segoe UI.
- Review: fixed SQL clauses only, no schema/dependency changes, existing sort callers
  retain Default, and current-item restoration does not add unselected cards.
- Installer, clean-machine, in-game overlay, and high-DPI/multi-monitor acceptance were
  not exercised for this change. These implementation checks preceded commit and CI
  verification; no official release was created.

## Commit boundaries

1. Library sort contract, storage implementation, and storage regression tests.
2. Persistent accessible sort control and dashboard selection/keyboard tests.
3. README and the scoped implementation/verification record.

## Delivery verification (2026-10-20)

- Fetched origin/main before committing; the starting checkout matched the remote.
- Exported staged snapshots isolate each code commit from later working-tree changes.
- Storage snapshot: all 296 tests and Ruff passed on Python 3.12, offscreen, exit zero.
- Interface snapshot: all 308 tests passed with native Windows Qt on Python 3.12
  (30.91s) and Python 3.11 (28.98s), serial runs with process exit zero. Ruff passed.
- Version metadata remains synchronized at 0.1.0. Standard wheel packaging passed;
  archive integrity and inclusion of the sorting module were checked explicitly.
- No installer or clean-machine acceptance was added by these delivery checks.
