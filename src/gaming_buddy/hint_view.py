from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QStyle, QVBoxLayout, QWidget

from gaming_buddy.hint_cards import HintContent
from gaming_buddy.markdown_view import MarkdownPreview

SaveHintProgress = Callable[[HintContent, int], HintContent | None]


class HintView(QWidget):
    """Only put persisted, revealed stages into the Qt text document."""

    def __init__(self, save: SaveHintProgress | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._save = save
        self.hints: HintContent | None = None
        self._interactive = True
        self._generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        self.status.setAccessibleName("Hint progress")
        self.content = MarkdownPreview()
        self.content.setMinimumHeight(45)
        self.content.setAccessibleName("Revealed hints")
        self.reveal_button = QPushButton()
        self.reveal_button.setObjectName("primary")
        self.reveal_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        self.reveal_button.setToolTip("Reveal the next stage after saving your progress")
        self.reset_button = QPushButton("Start over")
        self.reset_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reset_button.setAccessibleName("Hide all hint stages")
        self.reset_button.setToolTip("Hide every stage without deleting the guide")
        self.reveal_button.clicked.connect(self._reveal)
        self.reset_button.clicked.connect(self._reset)
        layout.addWidget(self.status)
        layout.addWidget(self.content, 1)
        layout.addWidget(self.reveal_button)
        layout.addWidget(self.reset_button)
        self.set_hints(None)

    def set_hints(self, hints: HintContent | None) -> None:
        self._generation += 1
        self.hints = hints
        progress = hints.revealed if hints else 0
        self.status.setText(f"{progress} of 3 stages revealed" if hints else "No hint selected")
        self.content.set_markdown(hints.visible_text if hints and progress
                                  else "Reveal one hint at a time when you need it.")
        self.reveal_button.setText(("Reveal first hint", "Reveal more guidance",
                                    "Reveal full solution…", "All stages revealed")[progress])
        self.reveal_button.setAccessibleName(self.reveal_button.text())
        self._update_buttons()

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled
        self._update_buttons()

    def _update_buttons(self) -> None:
        enabled = self._interactive and self._save is not None and self.hints is not None
        self.reveal_button.setEnabled(enabled and self.hints.revealed < 3)
        self.reset_button.setEnabled(enabled and self.hints.revealed > 0)

    def _reveal(self) -> None:
        expected = self.hints
        generation = self._generation
        if expected is None or not self.reveal_button.isEnabled():
            return
        if expected.revealed == 2:
            choice = QMessageBox.question(
                self, "Reveal full solution?",
                "This reveals the final answer. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if choice != QMessageBox.StandardButton.Yes or self._generation != generation:
                return
        self._save_progress(expected, expected.revealed + 1)

    def _reset(self) -> None:
        if self.hints is not None and self.reset_button.isEnabled():
            self._save_progress(self.hints, 0)

    def _save_progress(self, expected: HintContent, target: int) -> None:
        if self._save is None or not self._interactive:
            return
        saved = self._save(expected, target)
        if saved is None:
            self.status.setText("Progress not saved. Reopen the card and try again.")
            return
        self.set_hints(saved)
