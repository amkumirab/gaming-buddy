from __future__ import annotations

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit

from gaming_buddy.card_editor import CardEditor
from gaming_buddy.checklist_editor import insert_checklist
from gaming_buddy.models import Card, CardKind


@pytest.mark.parametrize("source,expected", [
    ("Bring potion\n\nMap", "- [ ] Bring potion\n\n- [ ] Map"),
    ("- Potion\n- [X] Map", "- [ ] Potion\n- [X] Map"),
    ("  1. Item\n  + Other", "  - [ ] Item\n  - [ ] Other"),
    ("", "- [ ] "),
])
def test_selected_lines_become_tasks_in_one_undo_step(qt_application, source, expected):
    editor = QTextEdit()
    try:
        editor.setPlainText(source)
        editor.selectAll()
        insert_checklist(editor)
        assert editor.toPlainText() == expected
        editor.undo()
        assert editor.toPlainText() == source
    finally:
        editor.close()
        editor.deleteLater()


def test_toolbar_converts_only_selected_unicode_lines(qt_application):
    editor = CardEditor(Card(1, CardKind.NOTE, "Game", "Tasks", content="🧪 Intro\nPotion\nMap"))
    try:
        cursor = editor.content_input.textCursor()
        cursor.setPosition(editor.content_input.document().findBlockByNumber(1).position())
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        editor.content_input.setTextCursor(cursor)
        editor.markdown_actions["checklist"].trigger()
        assert editor.content_input.toPlainText() == "🧪 Intro\n- [ ] Potion\n- [ ] Map"
        editor.content_input.undo()
        assert editor.content_input.toPlainText() == "🧪 Intro\nPotion\nMap"
    finally:
        editor.close()
        editor.deleteLater()


def test_existing_task_states_are_not_reset_by_repeated_action(qt_application):
    editor = QTextEdit()
    try:
        source = "- [x] Potion\n- [ ] Map"
        editor.setPlainText(source)
        editor.selectAll()
        insert_checklist(editor)
        assert editor.toPlainText() == source
    finally:
        editor.close()
        editor.deleteLater()
