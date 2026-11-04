from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from gaming_buddy.models import Card

if TYPE_CHECKING:
    from gaming_buddy.dashboard import Dashboard


class CaptureTextController(QObject):
    def __init__(self, dashboard: Dashboard) -> None:
        super().__init__(dashboard)
        self.host = dashboard
        self.pending = False

    def start(self) -> None:
        host = self.host
        if (host._quitting or host._capture_in_progress or host._card_pack_dialog is not None
                or QApplication.activeModalWidget()):
            return
        existing = host._text_recognition_dialog
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return
        self.pending = True
        host.start_capture()
        if not host._capture_in_progress:
            self.cancel()

    def cancel(self) -> None:
        self.pending = False

    def review(self, card: Card) -> None:
        pending = self.pending
        self.cancel()
        if pending and not self.host._quitting:
            self.host._extract_image_text(card, preview_image=True)
