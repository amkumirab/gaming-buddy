# Compact quick panel

## Purpose and design

Provide a small, optional in-game entry point for Capture, Quick note, and Find. Reuse
the current dark theme, standard Qt icons, visible English labels and keyboard focus
states. The existing panel is the visual reference; no new icon or styling dependency.
Use a native movable tool window, a one-line elided game label and a single action row.
Expand the note editor only on request. Keep full-panel navigation available at all times.

## Behavior

- A new configurable global shortcut (Ctrl+Shift+Q by default), tray action and full
  panel button open/toggle the quick panel. Existing panel and finder shortcuts keep
  their meaning. Upgrade missing actions without stealing existing custom bindings.
- Only one instance of the quick panel exists. Escape/X hide it without quitting or
  discarding text. Full panel and quick panel replace each other's visible surface.
- Game label reflects the current profile, including automatic switches. Empty game
  names display General. Full names remain available in an accessible label/tooltip.
- Quick note edits the same draft as Dashboard. Save/Pin delegate to existing note
  operations, preserve multiline text, clear both editors only after success, and
  keep the draft on storage failure. Existing autosave and shutdown persistence apply.
- Capture delegates to the existing capture workflow. Hide the quick panel for both
  area and full-monitor captures, including global-hotkey captures. Cancellation returns
  to the originating surface. Keep-hidden/full-monitor behavior remains unchanged.
  Capture failures use the existing recovery dialog/full panel. Prevent reopening while
  capture, shutdown, card-pack import or an application-modal dialog is active.
- Find invokes the existing quick finder and dismisses the quick panel. Showing the
  full panel, entering focus mode and starting shutdown also dismiss it. Cancelled exit
  permits reopening without losing the draft.
- Remember the quick-panel position locally and clamp it to an available screen on
  reopening. No changes to workspace/card data, backup format, dependencies or version.

## Verification and slices

1. Shortcut upgrade/routing with regressions for missing actions, collisions and custom
   settings. Existing listener shutdown and settings tests remain enabled.
2. Dedicated Qt view/controller modules and focused UI/integration tests: native button
   and keyboard input, shared draft, persistence, failures, profile changes, capture,
   modal/shutdown admission, geometry and returning to the full panel.
3. English README and native visual checks at compact sizes and long profile names.
   Run full suites serially with process exit zero on Python 3.11 and 3.12, Ruff, version
   validation and wheel packaging. Real-game/clean-installer acceptance remains separate.

Source: src/gaming_buddy; tests: tests/. Follow existing typed snake_case functions,
Qt Signal connections and isolated QSettings fixtures. Use python -X faulthandler -m
pytest, python -m ruff check --no-cache ., python scripts/validate_release.py and python
-m pip wheel --no-deps --wheel-dir build/verification-wheels . from the project root.
Do not change CI, publish a release, or update main during implementation.
