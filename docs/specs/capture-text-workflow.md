# Capture and review screenshot text

## Goal

Let a player select a clue and review its locally recognized text in one operation.
Keep the lossless source screenshot even if recognition is unavailable, cancelled,
empty or incorrect. Save reviewed text on that same image card for Quick Finder.

## Behavior and boundaries

- Explicit Capture text action in the full panel, tray and Quick Panel capture menu.
  Regular area/full-monitor capture and existing shortcuts retain their behavior.
- Reuse area selection, delay, native image saving and the existing recognition dialog.
  This explicit action saves the image without pinning or a separate capture review;
  it never rewrites the user's capture preferences. Cancelled selection saves nothing.
- Open a nonmodal, owned review window showing a thumbnail of the saved original,
  installed language choices, editable text, Copy, Save and Cancel. Text is plain text.
- Discover Windows languages and recognize text on the existing worker thread. The
  UI stays responsive; an unavailable pack, timeout or empty result permits retry or
  manual correction. No extra dependencies, external service or network upload.
- Only explicit Save writes text. Keep the dialog and corrections open if the database
  is unavailable or the card was deleted. Preserve the current card title, game and
  image; never create a second note/card. Cancel leaves image text unchanged.
- A second text capture while review exists raises that review rather than selecting
  another image. Block new work during capture, import, modal operation and shutdown.
  Reset pending intent on capture cancellation/failure and shutdown, so the next normal
  capture cannot accidentally trigger recognition. Existing worker shutdown drains apply.
- Keep Quick Panel compact: split capture control with the regular action on its body
  and an accessible arrow menu containing Capture text. Hide overlays before capture.
- English UI/docs. Follow existing theme and Qt ownership; no schema/version/CI changes.

## Build order and verification

1. Strengthen the recognition dialog: background language discovery, preview and
   explicit save confirmation, with worker/error/shutdown and UI tests.
2. Connect a small capture-text controller to existing successful/cancelled capture
   paths; add entry points and database/Quick Finder/capture regression tests.
3. Real-app lifecycle and local Windows OCR smoke check when available, native visual
   review, English README, serial Python 3.11/3.12 suites, Ruff and wheel verification.
   Record any untested installed-app, clean-machine and real-game scenarios explicitly.

Commands from the repository root (PowerShell):

```powershell
& .\.venv\Scripts\python.exe -X faulthandler -m pytest
& .\build\venv311\Scripts\python.exe -X faulthandler -m pytest
& .\.venv\Scripts\python.exe -m ruff check --no-cache .
& .\.venv\Scripts\python.exe scripts/validate_release.py
& .\.venv\Scripts\python.exe -m pip wheel --no-deps --wheel-dir build/verification-wheels .
```

Official Qt references:
https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QToolButton.html
https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDialog.html
https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html
