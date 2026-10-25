from __future__ import annotations

import sqlite3

import pytest
from PySide6.QtGui import QTextDocument

from gaming_buddy.models import Card, CardKind
from gaming_buddy.note_checklist import checklist_items, set_task
from gaming_buddy.storage import CardStore


def test_mapping_preserves_display_and_exact_source(qt_application):
    source = "# Route\r\n\r\n- [ ] 🧪 Bring **potion**\r\n- [X] Map\r\n\r\nKeep  spaces.\r\n"
    document = QTextDocument()
    tasks = checklist_items(source, document)
    assert len(tasks) == 2
    assert [item.checked for item in tasks] == [False, True]
    assert "Bring potion" in document.toPlainText()
    assert "gbtask" not in document.toPlainText()
    result = set_task(source, tasks[0].offset, True)
    assert result == source.replace("- [ ]", "- [x]", 1)
    assert set_task(result, tasks[0].offset, False) == source


@pytest.mark.parametrize("source", [
    "```md\n- [ ] code\n```", "~~~\n- [x] code\n~~~",
    "    - [ ] code", r"\- [ ] escaped", "Inline `- [ ] code`",
    "[ ] plain", "- [invalid] plain", "```\n- [ ]\n```",
    "> - [ ] quoted example",
])
def test_non_tasks_are_never_interactive(qt_application, source):
    document = QTextDocument()
    tasks = checklist_items(source, document)
    reference = QTextDocument()
    reference.setMarkdown(source)
    assert tasks == ()
    assert document.toPlainText() == reference.toPlainText()


def test_mixed_code_and_nested_tasks_map_only_actual_markers(qt_application):
    source = "- [ ] First\n  - [x] Nested\n\n```\n- [ ] First\n```\n\n- [ ] Last\n"
    document = QTextDocument()
    tasks = checklist_items(source, document)
    assert len(tasks) == 3
    assert [source[item.offset] for item in tasks] == [" ", "x", " "]
    result = set_task(source, tasks[-1].offset, True)
    assert result.endswith("- [x] Last\n")
    assert "```\n- [ ] First\n```" in result


def test_repeated_unicode_tasks_keep_distinct_source_offsets(qt_application):
    source = "# 🧪 Prep\n\n- [ ] 🧪 Potion\n- [ ] 🧪 Potion\n"
    document = QTextDocument()
    tasks = checklist_items(source, document)
    assert len(tasks) == 2
    assert set_task(source, tasks[1].offset, True) == "# 🧪 Prep\n\n- [ ] 🧪 Potion\n- [x] 🧪 Potion\n"


@pytest.mark.parametrize("offset", [-1, 0, 999, True])
def test_invalid_offsets_cannot_change_note(offset):
    with pytest.raises(ValueError):
        set_task("- [ ] Task", offset, True)


def test_note_update_is_conditional_and_preserves_other_fields(tmp_path):
    path = tmp_path / "cards.sqlite3"
    with CardStore(path) as store:
        card = store.add(Card(None, CardKind.NOTE, "Game", "Task", content="- [ ] Task\n",
                              tags=("boss",), favorite=True, pinned=True, locked=True))
        assert store.update_note_content(card.id, expected=card.content, content="- [x] Task\n")
        assert not store.update_note_content(card.id, expected=card.content, content="stale overwrite")
        saved = store.get(card.id)
        assert saved.content == "- [x] Task\n"
        assert saved.tags == card.tags and saved.favorite and saved.pinned and saved.locked
        assert saved.created_at == card.created_at
    with CardStore(path) as reopened:
        assert reopened.get(card.id).content == "- [x] Task\n"


def test_note_update_rejects_images_deleted_cards_and_rolls_back_failure(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        image = store.add(Card(None, CardKind.IMAGE, "Game", "Map", content="- [ ] text"))
        note = store.add(Card(None, CardKind.NOTE, "Game", "Task", content="- [ ] Task"))
        assert not store.update_note_content(image.id, expected=image.content, content="changed")
        store._connection.execute(
            "CREATE TRIGGER reject_task BEFORE UPDATE OF content ON cards "
            "BEGIN SELECT RAISE(ABORT, 'write failure'); END"
        )
        with pytest.raises(sqlite3.Error):
            store.update_note_content(note.id, expected=note.content, content="- [x] Task")
        assert store.get(note.id).content == note.content
        store.move_to_trash(note.id)
        assert not store.update_note_content(note.id, expected=note.content, content="changed")
