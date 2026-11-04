# Graceful shutdown tasks

- [x] Worker contracts: real-thread readiness, admission closure, cooperative download
  cancellation, and recognition auto-start prevention. Verify focused worker tests.
- [x] Exit coordination: nonblocking wait, 60-second timeout, cancellation, safe pending
  capture cancellation, final draft/layout persistence, and late-callback suppression.
  Verify coordinator and dashboard integration tests.
- [x] Runtime and documentation: busy-exit subprocess tests, English README, full
  Python 3.11/3.12 suites with process exit zero, Ruff, metadata and wheel build checks.
- [x] Checkpoint: review scoped changes and report untested installer/manual scenarios.

# Persistent library sorting

- [x] Storage: fixed sort choices, backward-compatible Default, deterministic ties,
  creation-date ordering, combined filters, and invalid-value regression tests.
- [x] Interface: accessible Sort by control, saved choice, stable selection/preview,
  keyboard interaction, empty states, and compact layout tests.
- [x] Delivery checks: English README, full Python 3.11/3.12 suites, Ruff, metadata,
  wheel packaging, and scoped code review. Report any untested desktop scenarios.

# Shared card packs

- [x] Reader: strict bounded ZIP/JSON/image validation, immutable preview records,
  existing exporter compatibility, missing-image reporting and malicious-input tests.
- [x] Writer: atomic batch insertion, duplicate detection, destination game, original
  byte preservation and injected failure/cleanup tests without existing-data changes.
- [x] Interface: accessible offline preview and selection, library entry point,
  cancellation/shutdown guards and dashboard integration tests.
- [x] Verification: English README, full Python 3.11/3.12 suites, Ruff, metadata,
  wheel packaging, native Qt visual QA and independent review of sensitive paths.

# Interactive note checklists

- [x] Source mapping and atomic content updates: exact one-character changes, parser
  exclusions, stale/deleted/image protection, rollback and persistence tests.
- [x] Editor: Checklist toolbar action and quick-note helper; selection, Unicode,
  existing task states, ordinary notes and one-step undo regression tests.
- [x] Pins: mouse/keyboard interaction, progress, save failure, library synchronization,
  click-through and shutdown guards with integration tests.
- [x] Verification: English README, full serial Python 3.11/3.12 suites with exit zero,
  Ruff, metadata, wheel packaging, native Qt visual review and scoped source review.

# Release candidate handoff

- [x] Fresh manual main build investigation: reproduced registry contamination in run
  41031956975; isolate installer tests on a fresh runner without weakening data guards.
- [x] Corrected branch build: successful automated lifecycle checks; download and
  independently verify installer/checksum against the exact Actions source SHA.
- [x] Python-free report preparation: input verification, non-overwriting output,
  candidate/environment identity and real PowerShell subprocess regression tests.
- [x] Compatibility/performance test procedure, English docs, source review, full
  serial Python 3.11/3.12 suites, Ruff and release metadata verification.
- [ ] External acceptance: clean Windows without Python and representative real games;
  actual installation, interaction, retention and performance evidence before release.

# Compact quick panel

- [x] Shortcut: new configurable action, collision-safe upgrade and listener/app routing.
- [x] View/coordinator: compact accessible controls, shared draft and game label, existing
  save/pin/finder paths, capture/modal/shutdown lifecycle and remembered safe position.
- [x] Verification: focused behavioral regressions, native visual/keyboard checks,
  English README, full serial Python 3.11/3.12 suites, Ruff, metadata and wheel build.

# Interactive first-run walkthrough

- [x] Progress: persistent steps, skipped outcomes, pause/resume and practice note ID,
  with safe settings parsing and keyboard-accessible, wrapping step cards.
- [x] Integration: existing editor, pin, capture and Quick Panel paths; first-run upgrade
  behavior, reference guide, failed writes, deleted notes, busy/modal and shutdown guards.
- [x] Verification: real-app restart/exit, native small-window layout, full serial
  Python 3.11/3.12 suites, Ruff, metadata, wheel packaging and scoped code review.

# Capture and review screenshot text

- [x] Review: background language discovery, literal plain text, original-image preview,
  explicit save confirmation and recoverable storage errors with focused tests.
- [x] Capture flow: shared split capture button and controller, full/quick/tray entry
  points, original image retention, one review, cancellation and busy/shutdown guards.
- [x] Verification: real Windows OCR fixture, native layouts, real-app normal/busy
  shutdown, serial Python 3.11/3.12 suites, Ruff, metadata, wheel and source review.

# Production readiness audit

- [x] Baseline, architecture/feature inventory, packaging/distribution review and
  reproducible-issue prioritization; preserve local state and existing licensing.
- [x] Atomic card/tag edits and retryable editor failures; checked with real SQLite
  constraint failures, database reopen and real Qt editor state/release tests.
- [x] Reject failed monitor snapshots; keep native/fractional scale and negative coordinates.
- [x] Preserve compact pin position/expanded size; allow all tabs in a 640px workspace.
- [x] Updated actual source screenshot, short dialog resource probe, complete audit
  report/manual checklist, 523 passing tests on both runtimes, Ruff and wheel build.
- [ ] External acceptance on clean Windows and real games before an official release.
