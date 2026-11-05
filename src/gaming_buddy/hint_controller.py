from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from gaming_buddy.hint_cards import HintContent
from gaming_buddy.hint_editor import HintEditor
from gaming_buddy.models import Card, CardKind

if TYPE_CHECKING:
    from gaming_buddy.dashboard import Dashboard


class HintCardController:
    def __init__(self, panel: Dashboard) -> None:
        self.panel = panel

    def create(self) -> None:
        panel = self.panel
        if panel._quitting or panel._capture_in_progress or panel._card_pack_dialog is not None:
            return
        card = Card(None, CardKind.NOTE, panel.game_input.text().strip() or "General", "",
                    height=360)
        dialog = HintEditor(card, panel)
        try:
            while dialog.exec() and not panel._quitting:
                card.title, card.game, _ = dialog.values()
                card.game = card.game or "General"
                card.tags = dialog.tags()
                card.hints = dialog.hint_content()
                try:
                    panel.store.add(card)
                except sqlite3.Error:
                    QMessageBox.warning(panel, "Hint card not saved",
                                        "Your guide is still in the editor. Check storage access "
                                        "and retry, or copy your text before cancelling.")
                    continue
                try:
                    panel.refresh_cards()
                except (sqlite3.Error, OSError):
                    panel.statusBar().showMessage("Hint card saved. Reopen the library to see it.",
                                                  5000)
                else:
                    panel.statusBar().showMessage(
                        "Hint card saved. Find it in the library under Notes.", 5000,
                    )
                return
        finally:
            dialog.deleteLater()

    def save_progress(self, card: Card, expected: HintContent, target: int) -> HintContent | None:
        panel = self.panel
        if (panel._quitting or card.id is None or panel._capture_in_progress
                or panel._card_pack_dialog is not None):
            return None
        try:
            if not panel.store.set_hint_progress(card.id, expected, target):
                return None
        except sqlite3.Error:
            panel.statusBar().showMessage("Hint progress could not be saved. Try again.", 4000)
            return None
        updated = expected.with_progress(target)
        card.hints = updated
        pin = panel.pins.get(card.id)
        if pin is not None and pin.hint_view is not None:
            pin.card.hints = updated
            pin.hint_view.set_hints(updated)
        preview_card = panel.card_preview.card
        if preview_card is not None and preview_card.id == card.id:
            preview_card.hints = updated
            panel.card_preview.set_card(preview_card)
        return updated
