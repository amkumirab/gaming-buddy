# Interactive first-run walkthrough

## Goal and scope

Help a new user save a real note, pin it, save a screenshot, and open Quick Panel.
Use a small, nonmodal card inside the full panel, following existing section styles.
Keep the existing reference guide and startup preference available. No dependencies,
database migrations, telemetry, sample cards, or separate capture/storage paths.

## Behavior

- Show automatically for new installations only. Respect the existing
  `onboarding/completed` flag on upgrades; Help can start/resume the new walkthrough.
- Four steps: save a note, pin a note, capture a screenshot, open Quick Panel.
  Advance only on successful operations while the walkthrough is active. Save-and-pin
  can satisfy both note steps. Restoring saved pins must not count as user practice.
- Persist the current step, skipped steps, pause state, and practice note ID in QSettings.
  Pause hides the card; Help resumes. Each step may be skipped. A completion summary
  distinguishes completed and skipped steps. Restart resets only guide progress.
- Actions use the normal editor, stored note, capture workflow, and Quick Panel.
  Never replace an existing draft or modify capture preferences. If a practice note
  was deleted, explain recovery and let the user write another note or skip.
- Capturing hides the guide with the dashboard. Cancellation and failures do not
  advance. Respect existing keep-hidden and Quick Panel behavior; never steal focus
  after a background save. Show current shortcut bindings, not hardcoded defaults.
- All UI/docs English, keyboard-accessible buttons, wrapping plain-text labels,
  owned Qt widgets and no new timers. Normal shutdown must exit with code zero.

## Implementation and checks

1. Add progress model and compact view, with focused state/UI tests.
2. Add a controller and minimal successful-operation hooks to the existing workflows;
   test real database writes, failed writes, capture cancellation, pause and resume.
3. Verify lifecycle, native layout, full suites on Python 3.11/3.12, Ruff and packaging;
   document operation and untested hardware scenarios.

Commands (PowerShell, repository root):

```powershell
& .\.venv\Scripts\python.exe -X faulthandler -m pytest
& .\build\venv311\Scripts\python.exe -X faulthandler -m pytest
& .\.venv\Scripts\python.exe -m ruff check --no-cache .
& .\.venv\Scripts\python.exe scripts/validate_release.py
& .\.venv\Scripts\python.exe -m pip wheel --no-deps --wheel-dir build/verification-wheels .
```

Official Qt ownership reference:
https://doc.qt.io/qtforpython-6/overviews/qtcore-objecttrees.html
