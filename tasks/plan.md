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
