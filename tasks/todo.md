# Graceful shutdown tasks

- [x] Worker contracts: real-thread readiness, admission closure, cooperative download
  cancellation, and recognition auto-start prevention. Verify focused worker tests.
- [x] Exit coordination: nonblocking wait, 60-second timeout, cancellation, safe pending
  capture cancellation, final draft/layout persistence, and late-callback suppression.
  Verify coordinator and dashboard integration tests.
- [x] Runtime and documentation: busy-exit subprocess tests, English README, full
  Python 3.11/3.12 suites with process exit zero, Ruff, metadata and wheel build checks.
- [x] Checkpoint: review scoped changes and report untested installer/manual scenarios.
