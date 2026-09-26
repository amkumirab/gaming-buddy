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
        tags=("code", "puzzle"),
    )
    editor = CardEditor(card)

    assert editor.content_input is not None
    assert editor.content_input.toPlainText() == "SAFE CODE 0451"
    editor.content_input.setPlainText("SAFE CODE 0421")

    assert editor.values() == ("Safe", "Control", "SAFE CODE 0421")
    assert editor.tags() == ("code", "puzzle")
    editor.tags_input.setText(" Map,  boss ; MAP, #route ")
    assert editor.tags() == ("Map", "boss", "route")
    editor.close()


@pytest.mark.parametrize("kind", [CardKind.NOTE, CardKind.IMAGE])
def test_multiline_content_is_preserved_when_opened_and_saved(
    application: QApplication,
    kind: CardKind,
) -> None:
    content = "First objective\n\nSecond objective\n  - Keep this indentation"
    card = Card(
        1,
        kind,
        "Control",
        "Mission notes",
        content=content,
        image_path="mission.png" if kind is CardKind.IMAGE else "",
    )

    editor = CardEditor(card)

    assert editor.content_input.toPlainText() == content
    assert editor.values() == ("Mission notes", "Control", content)
    editor.close()


def test_note_markdown_preview_updates_without_changing_source(
    application: QApplication,
) -> None:
    source = "# Boss route\n\n- Dodge left\n- Use **fire**"
    card = Card(1, CardKind.NOTE, "Control", "Route", content=source)
    editor = CardEditor(card)

    assert editor.content_tabs is not None
    assert editor.markdown_preview is not None
    editor.content_tabs.setCurrentWidget(editor.markdown_preview)

    assert editor.markdown_preview.toPlainText() == "Boss route\nDodge left\nUse fire"
    assert editor.content_input.toPlainText() == source
    assert editor.values() == ("Route", "Control", source)

    editor.content_input.setPlainText("## Updated\n\n`code`")
    assert editor.markdown_preview.toPlainText() == "Updated\ncode"
    assert editor.values()[2] == "## Updated\n\n`code`"
    editor.close()


def test_image_text_editor_remains_plain_text(application: QApplication) -> None:
    source = "# Extracted heading\n**Keep markers**"
    card = Card(1, CardKind.IMAGE, "Control", "Clue", content=source)
    editor = CardEditor(card)

    assert editor.content_tabs is None
    assert editor.markdown_preview is None
    assert editor.content_input.toPlainText() == source
    editor.close()
