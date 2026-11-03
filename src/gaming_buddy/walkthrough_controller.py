from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication

from gaming_buddy.models import Card, CardKind
from gaming_buddy.walkthrough import STEP_COUNT, WalkthroughProgress

if TYPE_CHECKING:
    from gaming_buddy.dashboard import Dashboard


class WalkthroughController(QObject):
    def __init__(self, dashboard: Dashboard) -> None:
        super().__init__(dashboard)
        self.host = dashboard
        self.panel = dashboard.walkthrough_panel
        self.progress = WalkthroughProgress.load(dashboard.settings)
        self.panel.action_requested.connect(self.act)
        self.panel.skip_requested.connect(self.skip)
        self.panel.pause_requested.connect(self.pause)
        self.panel.reference_requested.connect(dashboard.show_reference_guide)
        dashboard.shortcuts_changed.connect(self.render)
        dashboard.shutdown_started.connect(self._shutdown_started)
        dashboard.shutdown_cancelled.connect(self._shutdown_cancelled)

    def _allowed(self) -> bool:
        return not (self.host._quitting or self.host._capture_in_progress
                    or self.host._card_pack_dialog is not None or QApplication.activeModalWidget())

    @property
    def active(self) -> bool:
        return not self.progress.paused and not self.host._quitting

    def start(self) -> bool:
        if not self._allowed():
            return False
        self.progress.paused = False
        self._save_and_render()
        self.host.show_panel()
        self.panel.show()
        self.panel.action_button.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def pause(self) -> None:
        self.progress.paused = True
        self.progress.save(self.host.settings)
        self.panel.hide()

    def skip(self) -> None:
        if self.active and self._allowed():
            self.progress.advance(skip=True)
            self._save_and_render()

    def _save_and_render(self) -> None:
        self.progress.save(self.host.settings)
        self.render()

    def render(self) -> None:
        keys = self.host.shortcuts
        steps = (
            ("Save your first note",
             ("Write a clue in the normal note editor, then choose Save note or Pin note. "
              "Your existing draft will stay intact."), "Write note"),
            ("Keep a note on screen",
             ("Pin the note you just saved. Move its window beside your game and resize it. "
              "You can also pin any saved note from the Library."), "Pin note"),
            ("Capture a clue",
             (f"Choose Capture or press {keys['capture_area']}, then drag around a small area. "
              f"Save the screenshot; cancel any time with Escape. Return with {keys['toggle_panel']} "
              "if your capture settings keep the panel hidden."), "Capture"),
            ("Try Quick Panel",
             (f"Open the compact controls here or press {keys['toggle_quick_panel']}. "
              f"Use Full panel or {keys['toggle_panel']} to return. For games, Borderless Windowed "
              "mode works best; exclusive fullscreen may hide overlays."), "Quick panel"),
            ("You're ready",
             (f"{STEP_COUNT - len(self.progress.skipped)} completed; "
              f"{len(self.progress.skipped)} skipped. Your notes and screenshots stay in the Library. "
              "Reopen this walkthrough from Help at any time."), "Restart"),
        )
        self.panel.set_step(self.progress.step, *steps[self.progress.step])

    def act(self) -> None:
        if not self.active or not self._allowed():
            return
        step = self.progress.step
        if step == STEP_COUNT:
            self.progress = WalkthroughProgress(paused=False)
            self._save_and_render()
        elif step == 0:
            self._focus_editor()
        elif step == 1:
            try:
                card = self.host.store.get(self.progress.note_id) if self.progress.note_id else None
                if card is not None and card.kind is CardKind.NOTE:
                    self.host.show_pin(card)
                    return
            except sqlite3.Error:
                self.panel.description.setText(
                    "The note could not be opened or pinned. Check storage access and try again."
                )
                return
            self.panel.description.setText(
                "The practice note is unavailable. Write another note and choose Pin note, "
                "or pin an existing note from the Library. You can also skip this step."
            )
            self._focus_editor()
        elif step == 2:
            self.host.start_capture()
        elif step == 3:
            self.host.show_quick_panel()

    def _focus_editor(self) -> None:
        self.host.main_tabs.setCurrentIndex(0)
        self.host.capture_scroll.ensureWidgetVisible(self.host.note_input)
        self.host.note_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def note_saved(self, card: Card) -> None:
        if not self.active or self.progress.step not in (0, 1):
            return
        self.progress.note_id = card.id
        if self.progress.step == 0:
            self.progress.advance()
        self._save_and_render()

    def pin_shown(self, card: Card) -> None:
        if self.active and self.progress.step == 1 and card.kind is CardKind.NOTE:
            self.progress.advance()
            self._save_and_render()

    def capture_saved(self) -> None:
        if self.active and self.progress.step == 2:
            self.progress.advance()
            self._save_and_render()

    def quick_panel_opened(self) -> None:
        if self.active and self.progress.step == 3:
            self.progress.advance()
            self._save_and_render()

    def _shutdown_started(self) -> None:
        self.panel.setEnabled(False)

    def _shutdown_cancelled(self) -> None:
        self.panel.setEnabled(True)
