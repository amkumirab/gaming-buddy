"""Interactive native task markers with save-before-display behavior."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from gaming_buddy.markdown_view import MarkdownPreview, contains_markdown
from gaming_buddy.note_checklist import ChecklistItem, checklist_items, set_task


class ChecklistView(MarkdownPreview):
    progress_changed = Signal(int, int)
    save_failed = Signal()

    def __init__(self, save: Callable[[str, str], bool] | None = None) -> None:
        super().__init__()
        self._save = save
        self._interactive = True
        self.source = ""
        self.items: tuple[ChecklistItem, ...] = ()
        self._pressed: tuple[int, QPoint] | None = None
        self.setTextInteractionFlags(
            self.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.setAccessibleName("Pinned note checklist")
        self.setAccessibleDescription(
            "Click a checkbox, or move the text cursor to a task line and press Space. "
            "Changes are saved immediately. Select text to copy without changing tasks."
        )

    def set_markdown(self, source: str) -> None:
        self.source = source
        if contains_markdown(source):
            self.items = checklist_items(source, self.document())
        else:
            super().set_markdown(source)
            self.items = ()
        self.progress_changed.emit(sum(item.checked for item in self.items), len(self.items))

    def _marker_at(self, point: QPoint) -> int | None:
        position = point + QPoint(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        block = self.document().documentLayout().blockWithMarkerAt(position)
        return next((index for index, item in enumerate(self.items) if item.block == block), None)

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled
        self._pressed = None

    def _toggle(self, index: int) -> None:
        if self._save is None or not self._interactive:
            return
        item = self.items[index]
        updated = set_task(self.source, item.offset, not item.checked)
        if not self._save(self.source, updated):
            self.save_failed.emit()
            return
        scroll = self.verticalScrollBar().value()
        self.set_markdown(updated)
        self.setTextCursor(QTextCursor(self.items[index].block))
        self.verticalScrollBar().setValue(scroll)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._pressed = None
        index = self._marker_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and index is not None:
            self._pressed = index, event.position().toPoint()
            self.setFocus()
            self.setTextCursor(QTextCursor(self.items[index].block))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        pressed, self._pressed = self._pressed, None
        if pressed is not None:
            index, point = pressed
            if (event.button() == Qt.MouseButton.LeftButton
                    and (event.position().toPoint() - point).manhattanLength() < QApplication.startDragDistance()
                    and self._marker_at(event.position().toPoint()) == index):
                self._toggle(index)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._marker_at(event.position().toPoint()) is not None:
            self._pressed = None
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (event.key() == Qt.Key.Key_Space and not event.modifiers()
                and not self.textCursor().hasSelection()):
            index = next((index for index, item in enumerate(self.items)
                          if item.block == self.textCursor().block()), None)
            if index is not None:
                if not event.isAutoRepeat():
                    self._toggle(index)
                event.accept()
                return
        super().keyPressEvent(event)
