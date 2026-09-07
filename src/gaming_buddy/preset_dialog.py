from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.workspace_presets import WorkspacePresetSummary


class PresetAction(StrEnum):
    APPLY = "apply"
    SAVE = "save"
    RENAME = "rename"
    DELETE = "delete"


class WorkspacePresetDialog(QDialog):
    def __init__(
        self,
        game: str,
        presets: list[WorkspacePresetSummary],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.action: PresetAction | None = None
        self.setWindowTitle(f"Workspace layouts · {game}")
        self.setModal(True)
        self.resize(500, 380)

        layout = QVBoxLayout(self)
        intro = QLabel(
            f"Save and restore pin arrangements for {game}. Layouts reuse your existing "
            "cards and screenshots."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        for preset in presets:
            marker = "●  " if preset.active else ""
            suffix = "pin" if preset.pin_count == 1 else "pins"
            item = QListWidgetItem(f"{marker}{preset.name}  ·  {preset.pin_count} {suffix}")
            item.setData(Qt.ItemDataRole.UserRole, preset.id)
            item.setToolTip("Currently active" if preset.active else "")
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(
            lambda _item: self._choose(PresetAction.APPLY)
        )
        layout.addWidget(self.list, 1)

        actions = QHBoxLayout()
        save_button = QPushButton("Save current as…")
        save_button.clicked.connect(lambda: self._choose(PresetAction.SAVE))
        self.apply_button = QPushButton("Apply selected")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(lambda: self._choose(PresetAction.APPLY))
        self.rename_button = QPushButton("Rename…")
        self.rename_button.clicked.connect(lambda: self._choose(PresetAction.RENAME))
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(lambda: self._choose(PresetAction.DELETE))
        actions.addWidget(save_button)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.rename_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)

        has_presets = self.list.count() > 0
        for button in (self.apply_button, self.rename_button, self.delete_button):
            button.setEnabled(has_presets)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def selected_preset_id(self) -> int | None:
        item = self.list.currentItem()
        return int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _choose(self, action: PresetAction) -> None:
        if action is not PresetAction.SAVE and self.selected_preset_id is None:
            return
        self.action = action
        self.accept()
