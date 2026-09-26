from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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
        if card.kind is CardKind.NOTE:
            self.content_input.setMinimumHeight(150)
            self.content_input.setPlaceholderText(
                "Write a note using Markdown for headings, lists, emphasis, and code."
            )
            self.content_tabs = QTabWidget()
            self.content_tabs.addTab(self.content_input, "Write")
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
