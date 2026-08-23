from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ProfileDialog(QDialog):
    def __init__(self, profiles: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Game profiles")
        self.setModal(True)
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Linked executables switch Gaming Buddy to the matching game profile. "
            "Profile names can be edited here."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(("Game profile", "Executable"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for executable, game in sorted(profiles.items(), key=lambda item: item[1].casefold()):
            self._add_row(game, executable)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        remove_button = QPushButton("Remove selected")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._remove_selected)
        actions.addWidget(remove_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def profiles(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for row in range(self.table.rowCount()):
            game_item = self.table.item(row, 0)
            executable_item = self.table.item(row, 1)
            if game_item is not None and executable_item is not None:
                values[executable_item.text()] = game_item.text().strip()
        return values

    def accept(self) -> None:
        if any(not game for game in self.profiles().values()):
            QMessageBox.warning(self, "Profile name required", "Every profile needs a game name.")
            return
        super().accept()

    def _add_row(self, game: str, executable: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(game))
        executable_item = QTableWidgetItem(executable)
        executable_item.setFlags(executable_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 1, executable_item)

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
