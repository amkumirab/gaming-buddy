from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

from gaming_buddy.checklist_view import ChecklistView


def marker_point(view, index=0):
    task = view.items[index]
    rectangle = view.cursorRect(QTextCursor(task.block))
    for x in range(max(0, rectangle.x() - 40), rectangle.x()):
        point = QPoint(x, rectangle.center().y())
        block = view.document().documentLayout().blockWithMarkerAt(
            point + QPoint(view.horizontalScrollBar().value(), view.verticalScrollBar().value())
        )
        if block == task.block:
            return point
    raise AssertionError("No visible task marker")


def test_marker_click_saves_exact_source_and_updates_count(qt_application):
    writes, progress = [], []

    def save(before, after):
        writes.append((before, after))
        return True

    view = ChecklistView(save)
    try:
        source = "# Route\n\n- [ ] Potion\n- [x] Map\n"
        view.progress_changed.connect(lambda done, total: progress.append((done, total)))
        view.set_markdown(source)
        view.resize(360, 240)
        view.show()
        QTest.qWait(20)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=marker_point(view))
        assert writes == [(source, source.replace("[ ]", "[x]", 1))]
        assert view.source == writes[0][1]
        assert progress[-1] == (2, 2)
        assert not view.openLinks() and not view.openExternalLinks()
    finally:
        view.close()
        view.deleteLater()


def test_space_toggles_current_task_but_not_selected_text(qt_application):
    view = ChecklistView(lambda *_: True)
    try:
        view.set_markdown("- [ ] Potion\n- [ ] Map")
        cursor = QTextCursor(view.items[1].block)
        view.setTextCursor(cursor)
        QTest.keyClick(view, Qt.Key.Key_Space)
        assert view.source == "- [ ] Potion\n- [x] Map"
        view.selectAll()
        QTest.keyClick(view, Qt.Key.Key_Space)
        assert view.source == "- [ ] Potion\n- [x] Map"
    finally:
        view.close()
        view.deleteLater()


def test_failed_save_keeps_source_state_and_count(qt_application):
    errors = []
    view = ChecklistView(lambda *_: False)
    try:
        source = "- [ ] Potion"
        view.save_failed.connect(lambda: errors.append(True))
        view.set_markdown(source)
        view.setTextCursor(QTextCursor(view.items[0].block))
        QTest.keyClick(view, Qt.Key.Key_Space)
        assert errors == [True]
        assert view.source == source
        assert not view.items[0].checked
    finally:
        view.close()
        view.deleteLater()


@pytest.mark.parametrize("source", ["First\nSecond\n\nLast", "# Heading\n\n**bold**"])
def test_non_checklist_notes_keep_existing_display(qt_application, source):
    from gaming_buddy.markdown_view import MarkdownPreview

    view, reference = ChecklistView(lambda *_: True), MarkdownPreview()
    try:
        view.set_markdown(source)
        reference.set_markdown(source)
        assert not view.items
        assert view.toPlainText() == reference.toPlainText()
    finally:
        view.close()
        reference.close()
        view.deleteLater()
        reference.deleteLater()
