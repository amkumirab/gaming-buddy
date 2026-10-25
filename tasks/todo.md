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
