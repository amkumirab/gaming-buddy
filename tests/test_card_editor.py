from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
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
    assert editor.markdown_toolbar is None
    assert editor.markdown_actions == {}
    assert editor.markdown_shortcuts == []
    assert editor.content_input.toPlainText() == source
    editor.close()


def _select_text(editor: CardEditor, start: int, end: int) -> None:
    cursor = editor.content_input.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    editor.content_input.setTextCursor(cursor)


@pytest.mark.parametrize(
    ("action", "source", "start", "end", "expected"),
    [
        ("bold", "Use fire", 4, 8, "Use **fire**"),
        ("italic", "Dodge left", 6, 10, "Dodge *left*"),
        ("code", "Code 0421", 5, 9, "Code `0421`"),
    ],
)
def test_inline_toolbar_actions_wrap_selected_text(
    application: QApplication,
    action: str,
    source: str,
    start: int,
    end: int,
    expected: str,
) -> None:
    editor = CardEditor(Card(1, CardKind.NOTE, "Control", "Note", content=source))
    _select_text(editor, start, end)

    editor.markdown_actions[action].trigger()

    assert editor.content_input.toPlainText() == expected
    editor.close()


def test_inline_toolbar_action_inserts_and_selects_placeholder(
    application: QApplication,
) -> None:
    editor = CardEditor(Card(1, CardKind.NOTE, "Control", "Note", content="Use "))
    cursor = editor.content_input.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.content_input.setTextCursor(cursor)

    editor.markdown_actions["bold"].trigger()

    assert editor.content_input.toPlainText() == "Use **bold text**"
    assert editor.content_input.textCursor().selectedText() == "bold text"
    editor.close()


def test_line_toolbar_actions_apply_to_multiple_lines_and_toggle_off(
    application: QApplication,
) -> None:
    editor = CardEditor(
        Card(1, CardKind.NOTE, "Control", "Route", content="First\nSecond\nThird")
    )
    _select_text(editor, 0, len("First\nSecond"))

    editor.markdown_actions["list"].trigger()
    assert editor.content_input.toPlainText() == "- First\n- Second\nThird"

    editor.markdown_actions["list"].trigger()
    assert editor.content_input.toPlainText() == "First\nSecond\nThird"
    editor.close()


def test_line_toolbar_action_inserts_prefix_on_empty_line(
    application: QApplication,
) -> None:
    editor = CardEditor(Card(1, CardKind.NOTE, "Control", "Route", content="First\n"))
    cursor = editor.content_input.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.content_input.setTextCursor(cursor)

    editor.markdown_actions["heading"].trigger()

    assert editor.content_input.toPlainText() == "First\n# "
    editor.close()


def test_link_action_uses_selected_text_and_selects_url(
    application: QApplication,
) -> None:
    editor = CardEditor(Card(1, CardKind.NOTE, "Control", "Guide", content="Open guide"))
    _select_text(editor, 5, 10)

    editor.markdown_actions["link"].trigger()

    assert editor.content_input.toPlainText() == "Open [guide](https://)"
    assert editor.content_input.textCursor().selectedText() == "https://"
    editor.close()


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (Qt.Key.Key_B, "Use **fire**"),
        (Qt.Key.Key_I, "Use *fire*"),
    ],
)
def test_formatting_keyboard_shortcuts_insert_markdown(
    application: QApplication,
    key: Qt.Key,
    expected: str,
) -> None:
    editor = CardEditor(Card(1, CardKind.NOTE, "Control", "Note", content="Use fire"))
    editor.show()
    editor.activateWindow()
    application.processEvents()
    _select_text(editor, 4, 8)
    editor.content_input.setFocus()
    application.processEvents()

    QTest.keyClick(editor.content_input, key, Qt.KeyboardModifier.ControlModifier)
    application.processEvents()

    assert editor.content_input.toPlainText() == expected
    editor.close()
