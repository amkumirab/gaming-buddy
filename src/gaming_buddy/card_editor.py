from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.checklist_editor import insert_checklist
from gaming_buddy.markdown_view import MarkdownPreview
from gaming_buddy.models import Card, CardKind
from gaming_buddy.tags import MAX_TAG_LENGTH, MAX_TAGS_PER_CARD, normalize_tags


class CardEditor(QDialog):
    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card = card
        self.setWindowTitle("Edit card")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_input = QLineEdit(card.title)
        self.title_input.setMaxLength(120)
        self.game_input = QLineEdit(card.game)
        self.game_input.setMaxLength(80)
        self.tags_input = QLineEdit(", ".join(card.tags))
        self.tags_input.setMaxLength(420)
        self.tags_input.setPlaceholderText("map, boss, code, build…")
        self.tags_input.setToolTip(
            f"Separate tags with commas · up to {MAX_TAGS_PER_CARD} tags · "
            f"{MAX_TAG_LENGTH} characters each"
        )
        form.addRow("Title", self.title_input)
        form.addRow("Game", self.game_input)
        form.addRow("Tags", self.tags_input)

        self.content_input = QTextEdit()
        self.content_input.setPlainText(card.content)
        self.content_tabs: QTabWidget | None = None
        self.markdown_preview: MarkdownPreview | None = None
        self.markdown_toolbar: QToolBar | None = None
        self.markdown_actions: dict[str, QAction] = {}
        self.markdown_shortcuts: list[QShortcut] = []
        if card.kind is CardKind.NOTE:
            self.content_input.setMinimumHeight(150)
            self.content_input.setAcceptRichText(False)
            self.content_input.setPlaceholderText(
                "Write a note using Markdown for headings, lists, emphasis, and code."
            )
            self.content_tabs = QTabWidget()
            write_page = QWidget()
            write_layout = QVBoxLayout(write_page)
            write_layout.setContentsMargins(6, 6, 6, 6)
            write_layout.setSpacing(5)
            self.markdown_toolbar = self._create_markdown_toolbar()
            write_layout.addWidget(self.markdown_toolbar)
            write_layout.addWidget(self.content_input, 1)
            self.content_tabs.addTab(write_page, "Write")
            self.markdown_preview = MarkdownPreview()
            self.markdown_preview.setMinimumHeight(150)
            self.markdown_preview.setAccessibleName("Markdown note preview")
            self.content_tabs.addTab(self.markdown_preview, "Preview")
            self.content_tabs.currentChanged.connect(self._refresh_markdown_preview)
            self.content_input.textChanged.connect(self._refresh_visible_preview)
            form.addRow("Note", self.content_tabs)
        else:
            filename = Path(card.image_path).name or "Screenshot"
            file_label = QLabel(filename)
            file_label.setObjectName("muted")
            form.addRow("File", file_label)
            self.content_input.setMinimumHeight(130)
            self.content_input.setPlaceholderText(
                "Extracted screenshot text can be reviewed and corrected here."
            )
            form.addRow("Image text", self.content_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_markdown_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Note formatting")
        toolbar.setObjectName("markdownToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.setAccessibleName("Markdown formatting")

        self._add_markdown_action(
            toolbar,
            "bold",
            "B",
            "Bold (Ctrl+B)",
            lambda: self._wrap_selection("**", "bold text"),
            QKeySequence.StandardKey.Bold,
        )
        self._add_markdown_action(
            toolbar,
            "italic",
            "I",
            "Italic (Ctrl+I)",
            lambda: self._wrap_selection("*", "italic text"),
            QKeySequence.StandardKey.Italic,
        )
        toolbar.addSeparator()
        self._add_markdown_action(
            toolbar,
            "heading",
            "Heading",
            "Toggle heading for the selected lines",
            lambda: self._toggle_line_prefix("# "),
        )
        self._add_markdown_action(
            toolbar,
            "list",
            "List",
            "Toggle a bulleted list for the selected lines",
            lambda: self._toggle_line_prefix("- "),
        )
        self._add_markdown_action(
            toolbar,
            "quote",
            "Quote",
            "Toggle a quote for the selected lines",
            lambda: self._toggle_line_prefix("> "),
        )
        self._add_markdown_action(
            toolbar, "checklist", "Checklist", "Turn selected lines into checklist items",
            lambda: insert_checklist(self.content_input),
        )
        toolbar.addSeparator()
        self._add_markdown_action(
            toolbar,
            "code",
            "Code",
            "Format the selection as inline code",
            lambda: self._wrap_selection("`", "code"),
        )
        self._add_markdown_action(
            toolbar,
            "link",
            "Link",
            "Insert a Markdown link",
            self._insert_link,
        )
        return toolbar

    def _add_markdown_action(
        self,
        toolbar: QToolBar,
        name: str,
        label: str,
        tooltip: str,
        callback: Callable[[], None],
        shortcut: QKeySequence.StandardKey | None = None,
    ) -> None:
        action = QAction(label, self)
        action.setObjectName(f"markdown_{name}")
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)
        action.triggered.connect(callback)
        if shortcut is not None:
            key_sequence = QKeySequence(shortcut)
            note_shortcut = QShortcut(key_sequence, self.content_input)
            note_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            note_shortcut.activated.connect(action.trigger)
            self.markdown_shortcuts.append(note_shortcut)
        toolbar.addAction(action)
        self.markdown_actions[name] = action

    def _wrap_selection(self, marker: str, placeholder: str) -> None:
        cursor = self.content_input.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        value = selected or placeholder
        replacement = f"{marker}{value}{marker}"
        selection_start = cursor.selectionStart()

        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        cursor.setPosition(selection_start + len(marker))
        cursor.setPosition(
            selection_start + len(marker) + len(value),
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.content_input.setTextCursor(cursor)
        self.content_input.setFocus()

    def _toggle_line_prefix(self, prefix: str) -> None:
        cursor = self.content_input.textCursor()
        had_selection = cursor.hasSelection()
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        source = self.content_input.toPlainText()
        region_start = source.rfind("\n", 0, selection_start) + 1
        effective_end = max(selection_start, selection_end - 1) if had_selection else selection_end
        next_break = source.find("\n", effective_end)
        region_end = len(source) if next_break == -1 else next_break
        original = source[region_start:region_end]
        lines = original.split("\n")
        populated = [line for line in lines if line]
        remove_prefix = bool(populated) and all(line.startswith(prefix) for line in populated)
        if remove_prefix:
            transformed = "\n".join(line.removeprefix(prefix) for line in lines)
        elif not had_selection:
            transformed = prefix + original
        else:
            transformed = "\n".join(prefix + line if line else line for line in lines)

        replace_cursor = self.content_input.textCursor()
        replace_cursor.setPosition(region_start)
        replace_cursor.setPosition(region_end, QTextCursor.MoveMode.KeepAnchor)
        replace_cursor.beginEditBlock()
        replace_cursor.insertText(transformed)
        replace_cursor.endEditBlock()
        if had_selection:
            replace_cursor.setPosition(region_start)
            replace_cursor.setPosition(
                region_start + len(transformed),
                QTextCursor.MoveMode.KeepAnchor,
            )
        else:
            delta = len(transformed) - len(original)
            replace_cursor.setPosition(max(region_start, selection_start + delta))
        self.content_input.setTextCursor(replace_cursor)
        self.content_input.setFocus()

    def _insert_link(self) -> None:
        cursor = self.content_input.textCursor()
        selected = cursor.selectedText().replace("\u2029", " ") or "link text"
        replacement = f"[{selected}](https://)"
        selection_start = cursor.selectionStart()
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        url_start = selection_start + len(selected) + 3
        cursor.setPosition(url_start)
        cursor.setPosition(url_start + len("https://"), QTextCursor.MoveMode.KeepAnchor)
        self.content_input.setTextCursor(cursor)
        self.content_input.setFocus()

    def _refresh_markdown_preview(self, _index: int = 0) -> None:
        if self.markdown_preview is not None:
            self.markdown_preview.set_markdown(self.content_input.toPlainText())

    def _refresh_visible_preview(self) -> None:
        if (
            self.content_tabs is not None
            and self.markdown_preview is not None
            and self.content_tabs.currentWidget() is self.markdown_preview
        ):
            self._refresh_markdown_preview()

    def values(self) -> tuple[str, str, str]:
        content = self.content_input.toPlainText()
        return self.title_input.text().strip(), self.game_input.text().strip(), content

    def tags(self) -> tuple[str, ...]:
        return normalize_tags(self.tags_input.text())

    def accept(self) -> None:
        title, game, content = self.values()
        if not title:
            QMessageBox.warning(self, "Title required", "Enter a title for this card.")
            self.title_input.setFocus()
            return
        if self.card.kind is CardKind.NOTE and not content.strip():
            QMessageBox.warning(self, "Note required", "The note cannot be empty.")
            self.content_input.setFocus()
            return
        if not game:
            self.game_input.setText("General")
        super().accept()
