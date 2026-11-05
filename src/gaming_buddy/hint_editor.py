from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.hint_cards import MAX_HINT_LENGTH, STAGE_LABELS, HintContent
from gaming_buddy.models import Card
from gaming_buddy.tags import normalize_tags


class HintEditor(QDialog):
    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit hint card" if card.id is not None else "New hint card")
        self.setModal(True)
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        notice = QLabel("Authoring view: all three stages are available here. "
                        "Keep the title and tags free of spoilers.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        form = QFormLayout()
        self.title_input = QLineEdit(card.title)
        self.title_input.setMaxLength(120)
        self.game_input = QLineEdit(card.game)
        self.game_input.setMaxLength(80)
        self.tags_input = QLineEdit(", ".join(card.tags))
        self.tags_input.setMaxLength(420)
        self.tags_input.setPlaceholderText("puzzle, route, boss")
        form.addRow("Title", self.title_input)
        form.addRow("Game", self.game_input)
        form.addRow("Tags (comma-separated)", self.tags_input)
        layout.addLayout(form)
        tabs = QTabWidget()
        tabs.setObjectName("hintStageTabs")
        tabs.setAccessibleName("Hint authoring stages")
        self.steps: list[QTextEdit] = []
        for index, label in enumerate(STAGE_LABELS):
            field = QTextEdit()
            field.setAcceptRichText(False)
            field.setAccessibleName(label)
            field.setPlaceholderText(f"Write the {label.lower()} here. Markdown is supported.")
            if card.hints:
                field.setPlainText(card.hints.steps[index])
            tabs.addTab(field, label)
            tabs.setTabToolTip(index, f"Stage {index + 1} of 3: {label}")
            self.steps.append(field)
        layout.addWidget(tabs, 1)
        self.error = QLabel()
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                  | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        return self.title_input.text().strip(), self.game_input.text().strip(), ""

    def tags(self) -> tuple[str, ...]:
        return normalize_tags(self.tags_input.text().split(","))

    def hint_content(self) -> HintContent:
        return HintContent(tuple(field.toPlainText() for field in self.steps))

    def accept(self) -> None:
        if not self.title_input.text().strip():
            self.error.setText("Enter a spoiler-free title.")
            self.error.show()
            self.title_input.setFocus()
            return
        try:
            self.hint_content()
        except ValueError:
            self.error.setText(f"Fill in all three stages (up to {MAX_HINT_LENGTH:,} characters each).")
            self.error.show()
            return
        super().accept()
