from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.hotkeys import DEFAULT_SHORTCUTS, SHORTCUT_LABELS, validate_shortcuts


class ShortcutDialog(QDialog):
    def __init__(self, shortcuts: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Choose shortcuts that work from anywhere. Each shortcut must include "
            "at least one modifier key."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self._recorders: dict[str, QKeySequenceEdit] = {}
        for action, label in SHORTCUT_LABELS.items():
            recorder = QKeySequenceEdit(QKeySequence(shortcuts[action]), self)
            recorder.setMaximumSequenceLength(1)
            recorder.setClearButtonEnabled(True)
            self._recorders[action] = recorder
            form.addRow(label, recorder)
        layout.addLayout(form)

        restore_button = QPushButton("Restore defaults")
        restore_button.clicked.connect(self._restore_defaults)
        layout.addWidget(restore_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def shortcuts(self) -> dict[str, str]:
        return {
            action: recorder.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for action, recorder in self._recorders.items()
        }

    def accept(self) -> None:
        try:
            shortcuts = validate_shortcuts(self.shortcuts())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid shortcuts", str(exc))
            return
        for action, value in shortcuts.items():
            self._recorders[action].setKeySequence(QKeySequence(value))
        super().accept()

    def _restore_defaults(self) -> None:
        for action, shortcut in DEFAULT_SHORTCUTS.items():
            self._recorders[action].setKeySequence(QKeySequence(shortcut))
