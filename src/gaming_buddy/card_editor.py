from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.models import Card, CardKind


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
        form.addRow("Title", self.title_input)
        form.addRow("Game", self.game_input)

        self.content_input: QTextEdit | None = None
        if card.kind is CardKind.NOTE:
            self.content_input = QTextEdit(card.content)
            self.content_input.setMinimumHeight(150)
            form.addRow("Note", self.content_input)
        else:
            filename = Path(card.image_path).name or "Screenshot"
            file_label = QLabel(filename)
            file_label.setObjectName("muted")
            form.addRow("File", file_label)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        content = (
            self.content_input.toPlainText()
            if self.content_input is not None
            else self.card.content
        )
        return self.title_input.text().strip(), self.game_input.text().strip(), content

    def accept(self) -> None:
        title, game, content = self.values()
        if not title:
            QMessageBox.warning(self, "Title required", "Enter a title for this card.")
            self.title_input.setFocus()
            return
        if self.card.kind is CardKind.NOTE and not content.strip():
            QMessageBox.warning(self, "Note required", "The note cannot be empty.")
            assert self.content_input is not None
            self.content_input.setFocus()
            return
        if not game:
            self.game_input.setText("General")
        super().accept()
