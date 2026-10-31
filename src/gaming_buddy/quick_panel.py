from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QHideEvent, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class QuickPanel(QDialog):
    capture_requested = Signal()
    find_requested = Signal()
    full_panel_requested = Signal()
    save_requested = Signal(bool)
    hidden = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Gaming Buddy · Quick panel")
        self.setMinimumWidth(320)
        self._game = "General"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Quick panel")
        title.setObjectName("sectionTitle")
        self.full_panel_button = self._button("Full panel", "Open the full Gaming Buddy panel")
        self.full_panel_button.setObjectName("compact")
        self.full_panel_button.clicked.connect(self.full_panel_requested)
        header.addWidget(title, 1)
        header.addWidget(self.full_panel_button)
        layout.addLayout(header)
        self.game_label = QLabel()
        self.game_label.setTextFormat(Qt.TextFormat.PlainText)
        self.game_label.setObjectName("muted")
        self.game_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.game_label)
        actions = QHBoxLayout()
        self.capture_button = self._button("Capture", "Capture a screen region")
        self.note_button = self._button("Quick note", "Write a note for the current game")
        self.find_button = self._button("Find", "Find and pin a saved card")
        self.note_button.setCheckable(True)
        for button, icon in (
            (self.capture_button, QStyle.StandardPixmap.SP_DesktopIcon),
            (self.note_button, QStyle.StandardPixmap.SP_FileIcon),
            (self.find_button, QStyle.StandardPixmap.SP_FileDialogContentsView),
        ):
            button.setObjectName("compact")
            button.setIcon(self.style().standardIcon(icon))
            actions.addWidget(button, 1)
        layout.addLayout(actions)
        self.capture_button.clicked.connect(self.capture_requested)
        self.find_button.clicked.connect(self.find_requested)
        self.note_form = QWidget()
        form = QVBoxLayout(self.note_form)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        self.note_editor = QTextEdit()
        self.note_editor.setAcceptRichText(False)
        self.note_editor.setAccessibleName("Quick note draft")
        self.note_editor.setPlaceholderText("Write a clue, code, or checklist…")
        self.note_editor.setFixedHeight(160)
        form.addWidget(self.note_editor)
        buttons = QHBoxLayout()
        self.save_button = self._button("Save", "Save the note to the library")
        self.pin_button = self._button("Pin note", "Save and pin the note above the game")
        self.save_button.clicked.connect(lambda: self.save_requested.emit(False))
        self.pin_button.clicked.connect(lambda: self.save_requested.emit(True))
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.pin_button)
        form.addLayout(buttons)
        layout.addWidget(self.note_form)
        self.note_form.hide()
        self.note_button.toggled.connect(self._toggle_note)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status.setAccessibleName("Quick panel status")
        self.status.hide()
        layout.addWidget(self.status)
        self.set_game("")
        self.resize(360, self.sizeHint().height())

    @staticmethod
    def _button(text: str, description: str) -> QPushButton:
        button = QPushButton(text)
        button.setAutoDefault(False)
        button.setAccessibleName(text)
        button.setAccessibleDescription(description)
        button.setToolTip(description)
        return button

    def _toggle_note(self, expanded: bool) -> None:
        self.note_form.setVisible(expanded)
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())
        if expanded:
            self.note_editor.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def set_game(self, game: str) -> None:
        self._game = game.strip() or "General"
        self.game_label.setToolTip(self._game)
        self.game_label.setAccessibleName(f"Game: {self._game}")
        self._elide_game()

    def _elide_game(self) -> None:
        self.game_label.setText(self.game_label.fontMetrics().elidedText(
            f"Game: {self._game}", Qt.TextElideMode.ElideRight, self.game_label.width(),
        ))

    def show_status(self, message: str) -> None:
        self.status.setText(message if len(message) <= 160 else message[:157] + "…")
        self.status.setToolTip(message)
        self.status.setAccessibleDescription(message)
        self.status.setVisible(bool(message))
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._elide_game()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self.hidden.emit()
