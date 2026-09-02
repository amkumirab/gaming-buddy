from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from gaming_buddy.card_editor import CardEditor
from gaming_buddy.models import Card, CardKind


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_image_text_can_be_reviewed_and_edited(application: QApplication) -> None:
    card = Card(
        1,
        CardKind.IMAGE,
        "Control",
        "Safe",
        content="SAFE CODE 0451",
        image_path="safe.png",
    )
    editor = CardEditor(card)

    assert editor.content_input is not None
    assert editor.content_input.toPlainText() == "SAFE CODE 0451"
    editor.content_input.setPlainText("SAFE CODE 0421")

    assert editor.values() == ("Safe", "Control", "SAFE CODE 0421")
    editor.close()
