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

# Shared card packs (2026-10-23)

## Accepted scope and contracts

Import existing gaming-buddy-cards version 1 ZIP exports offline. Preview and select
cards before writing anything. Keep original game names by default, or choose one
destination game (blank means General). Preserve multiline text, tags, favorites,
and original image bytes. Missing-image cards are visible but not importable.
Skip exact live-card duplicates after applying the destination game; never overwrite
existing cards, settings, profiles, or layouts. Imported cards start unpinned.

The loader returns immutable in-memory card/image records, never extracted paths.
Only cards.json, optional README.md, and referenced images are accepted. Limits:
128 MiB ZIP, 256 MiB uncompressed, 4 MiB metadata, 1000 cards, 64 MiB per image,
32 million pixels per image, and 64 million pixels across the pack. Reject unsafe
paths, links, encryption, ambiguous names/JSON, unknown versions and corrupt images.
These are defensive resource bounds, not a claim that a shared pack is authenticated.

The writer takes validated records and selected indices. Card identity consists of
kind, destination game, title, exact content, normalized tags, and original-image
SHA-256. Favorites, creation dates and layout are not identity. Compare only active
cards; never read existing image paths outside the owned capture folder. New copies
use exclusive generated filenames. Batch database insertion is transactional; failure
rolls back all new cards/tags and removes only this operation's newly written copies.

## Ordered slices and verification

1. Reader and tests: real exporter round-trip, malformed metadata, unsafe members,
   duplicate names, byte/pixel limits, missing/corrupt images, immutable preview data.
2. Writer and storage tests: selected subset, destination game, duplicate import,
   unchanged edited notes, multi-card SQLite rollback, write failure cleanup.
3. Qt dialog and dashboard tests: checklist, offline preview, missing-image handling,
   game destination, cancel/error/success, shutdown re-entry guard, accessible controls.
4. README and verification record: full suites serially on Python 3.11 and 3.12,
   Ruff, synchronized version metadata, wheel build and native Qt visual review.

Source files live in src/gaming_buddy; isolated pytest cases live in tests. Follow
the existing typed dataclass, snake_case and Qt style conventions. Commands remain
`.venv/Scripts/python.exe -X faulthandler -m pytest`, `python -m ruff check .`,
`python scripts/validate_release.py`, and `python -m pip wheel --no-deps .`.
No schema, dependency, updater, release, or version changes. No network content is
loaded from a pack. Leave commits/push for the user's delivery request.

## Reader and lifecycle decisions

- Inspect the bounded raw central directory before constructing ZipFile, whose eager
  member parsing would otherwise precede file-count validation. Reject ZIP64 because
  current bounded exports do not need it and its alternate directory complicates limits.
- Read and validate the archive on a cancellable Python thread. Retain an immutable
  snapshot for preview; replacing the source archive cannot alter confirmed content.
- Plan duplicate detection on a worker using a snapshot of existing cards. Never pass
  the GUI-owned SQLite connection to the worker. Commit selected cards on the GUI thread.
- A modal preview pauses global shortcuts; queued capture requests are also rejected.
  Cancel and shutdown discard late results and wait for the real worker to finish.
- New image copies are registered immediately after exclusive creation, before stat or
  write. Failure cleanup checks file identity and never runs after a successful commit.

## Source receipts

- https://docs.python.org/3.12/library/zipfile.html#zipfile.ZipFile : ZIP member metadata,
  CRC checking during reads, and archive paths must not be treated as trusted filenames.
- https://doc.qt.io/qt-6/qimagereader.html : reader instances are reentrant; dimensions
  can be checked before decoding through a private QBuffer owned by the worker.
- https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection : connection context
  managers commit or roll back transactions; GUI-created connections stay on their thread.

## Intended commit boundaries

1. Bounded card-pack reader and malformed-input regression tests.
2. Duplicate planning, atomic storage insertion, and failure-cleanup tests.
3. Preview dialog, control-panel integration, keyboard and shutdown regression tests.
4. User documentation and verification record.

## Card-pack verification (2026-10-23)

- Final serial native Windows runs: 396 tests passed on Python 3.12.10 (39.27s)
  and Python 3.11.9 (37.47s), both process exit zero, with PySide6 6.12.0.
  The original 308 tests remain enabled; 88 new cases cover reader, writer, and UI.
- RED/GREEN checks reproduced missing preview/import interfaces, the ZIP64 directory
  bypass, queued capture interference, missing bounded thumbnails, and thread-start
  failure before implementing their fixes. Cancellation tests include Escape, the
  close button, explicit cancel, and shutdown while reading or planning.
- Independent design/backend review identified eager ZIP member parsing, ZIP64
  alternate-directory handling, GUI-thread blocking, and early file-identity failure.
  These paths now have explicit bounds, thread separation, and regression tests.
  Final UI integration was checked through source review, automated lifecycle tests,
  and native Qt rendering.
- Duplicate re-import creates no extra cards/files; changed multiline content remains
  distinct. Injected database, partial-write, close, and stat failures preserve existing
  cards and remove only newly owned copies. Refresh failure after commit keeps saved
  images. No SQLite connection is passed to the background reader/planner.
- Large-image thumbnails are decoded and prepared in the background. Resizing a wide
  preview fits the available width; imported files retain their original bytes.
- Reviewed native Qt renderings at 620x720 (text), 430x680 (image), and 470x730
  (Library). Isolated demonstration files and screenshots stay under ignored build/.
- Ruff, synchronized release metadata (unchanged 0.1.0), and the standard isolated
  wheel build passed. The final wheel's integrity, module inclusion, and source-byte
  equality were checked. No dependencies, database schema, or release workflow changed.
- This is local source/UI verification, not installed-app acceptance. PyInstaller,
  installer upgrade/uninstall, clean-machine, in-game, high-DPI/multi-monitor, and
  screen-reader acceptance were not run. No commit, push, tag, or release was created.

## Card-pack delivery checks (2026-10-23)

- Fetched origin/main before committing; the starting checkout matched the remote.
- Verified independent snapshots exported from the staged index, so later interface
  changes could not hide missing dependencies in earlier commits. The reader snapshot
  passed 357 tests and the writer snapshot passed 375 tests on Python 3.12, exit zero.
  Both snapshots passed Ruff.
- The interface snapshot passed all 396 tests serially on Python 3.12 (39.57s) and
  Python 3.11 (37.65s), with process exit zero. Ruff passed on the same snapshot.
- Reviewed staged implementation/test groups, public English text, ignored build
  artifacts, and the user guide. Release metadata remains synchronized at 0.1.0.
  The existing wheel's integrity and packaged source equality were rechecked.
- Delivery is organized as reader, transactional storage, interface, and documentation
  commits. These are source changes, not an installer release; the untested installed-app
  scenarios listed above remain outstanding. Remote CI is checked after pushing.
