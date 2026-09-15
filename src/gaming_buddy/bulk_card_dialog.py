from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.tags import MAX_TAG_LENGTH, MAX_TAGS_PER_CARD, normalize_tags


@dataclass(frozen=True, slots=True)
class BulkCardChanges:
    game: str | None
    add_tags: tuple[str, ...]
    remove_tags: tuple[str, ...]


class BulkCardDialog(QDialog):
    def __init__(
        self,
        selected_count: int,
        games: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Organize selected cards")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        title = QLabel(f"Organize {selected_count} selected cards")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        explanation = QLabel(
            "Move the cards to one game profile, add shared tags, or remove tags from all "
            "selected cards. Leave an option empty to keep it unchanged."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        self.move_game = QCheckBox("Move to game")
        self.game_input = QComboBox()
        self.game_input.setEditable(True)
        self.game_input.addItems(games)
        self.game_input.setCurrentText("")
        self.game_input.setEnabled(False)
        self.move_game.toggled.connect(self.game_input.setEnabled)
        game_row = QWidget()
        game_layout = QVBoxLayout(game_row)
        game_layout.setContentsMargins(0, 0, 0, 0)
        game_layout.addWidget(self.move_game)
        game_layout.addWidget(self.game_input)
        form.addRow("Game profile", game_row)

        self.add_tags_input = QLineEdit()
        self.add_tags_input.setMaxLength(420)
        self.add_tags_input.setPlaceholderText("map, boss, build…")
        self.remove_tags_input = QLineEdit()
        self.remove_tags_input.setMaxLength(420)
        self.remove_tags_input.setPlaceholderText("obsolete, old route…")
        tag_tip = (
            f"Separate tags with commas · up to {MAX_TAGS_PER_CARD} tags per card · "
            f"{MAX_TAG_LENGTH} characters each"
        )
        self.add_tags_input.setToolTip(tag_tip)
        self.remove_tags_input.setToolTip(tag_tip)
        form.addRow("Add tags", self.add_tags_input)
        form.addRow("Remove tags", self.remove_tags_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> BulkCardChanges:
        game = self.game_input.currentText().strip() if self.move_game.isChecked() else None
        if self.move_game.isChecked() and not game:
            raise ValueError("Enter a game name or turn off Move to game.")
        add_tags = normalize_tags(self.add_tags_input.text())
        remove_tags = normalize_tags(self.remove_tags_input.text())
        overlap = {tag.casefold() for tag in add_tags} & {
            tag.casefold() for tag in remove_tags
        }
        if overlap:
            raise ValueError("The same tag cannot be added and removed together.")
        if game is None and not add_tags and not remove_tags:
            raise ValueError("Choose at least one change for the selected cards.")
        return BulkCardChanges(game, add_tags, remove_tags)

    def accept(self) -> None:
        try:
            self.values()
        except ValueError as error:
            QMessageBox.warning(self, "No changes selected", str(error))
            return
        super().accept()
