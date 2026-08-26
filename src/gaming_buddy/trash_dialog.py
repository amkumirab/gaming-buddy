from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


def remove_card_image_if_unused(store: CardStore, card: Card, captures_dir: Path) -> bool:
    if card.kind is not CardKind.IMAGE or not card.image_path:
        return False
    if store.image_path_is_referenced(card.image_path):
        return False
    path = Path(card.image_path).resolve()
    if not path.is_relative_to(captures_dir.resolve()):
        return False
    if not path.is_file():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


class TrashDialog(QDialog):
    def __init__(
        self, store: CardStore, captures_dir: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.captures_dir = captures_dir
        self.setWindowTitle("Recently deleted")
        self.setMinimumSize(500, 480)
        self.resize(560, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Recently deleted")
        title.setObjectName("dialogTitle")
        description = QLabel(
            "Cards stay here for 30 days. Restore anything you still need before it is "
            "permanently removed."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search deleted cards…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)

        self.card_list = QListWidget()
        self.card_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.card_list.setWordWrap(True)
        self.card_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.card_list.itemSelectionChanged.connect(self._update_actions)
        layout.addWidget(self.card_list, 1)

        actions = QHBoxLayout()
        self.restore_button = QPushButton("Restore selected")
        self.restore_button.setObjectName("primary")
        self.restore_button.clicked.connect(self.restore_selected)
        self.delete_button = QPushButton("Delete permanently")
        self.delete_button.setObjectName("danger")
        self.delete_button.clicked.connect(self.delete_selected)
        self.empty_button = QPushButton("Empty trash")
        self.empty_button.setObjectName("danger")
        self.empty_button.clicked.connect(self.empty_trash)
        actions.addWidget(self.restore_button)
        actions.addWidget(self.delete_button)
        actions.addStretch(1)
        actions.addWidget(self.empty_button)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.card_list.clear()
        for card in self.store.list_deleted(self.search.text()):
            kind = "Screenshot" if card.kind is CardKind.IMAGE else "Note"
            game = card.game or "General"
            item = QListWidgetItem(
                f"{card.title}\n     {kind} · {game} · Deleted {_display_time(card.deleted_at)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, card.id)
            item.setToolTip("Select this card to restore it or delete it permanently")
            self.card_list.addItem(item)
        self._update_actions()

    def restore_selected(self) -> None:
        restored = 0
        for card in self._selected_cards():
            if card.id is not None and self.store.restore(card.id):
                restored += 1
        self.refresh()
        if restored:
            self._show_result(f"Restored {restored} card(s)")

    def delete_selected(self) -> None:
        cards = self._selected_cards()
        if not cards:
            return
        answer = QMessageBox.question(
            self,
            "Delete permanently",
            f"Permanently delete {len(cards)} selected card(s)?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        deleted = self._delete_cards(cards)
        self.refresh()
        if deleted:
            self._show_result(f"Permanently deleted {deleted} card(s)")

    def empty_trash(self) -> None:
        count = self.store.deleted_count()
        if not count:
            return
        answer = QMessageBox.question(
            self,
            "Empty trash",
            f"Permanently delete all {count} card(s) in the trash?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        cards = self.store.empty_trash()
        for card in cards:
            remove_card_image_if_unused(self.store, card, self.captures_dir)
        self.refresh()
        self._show_result(f"Permanently deleted {len(cards)} card(s)")

    def _selected_cards(self) -> list[Card]:
        cards: list[Card] = []
        for item in self.card_list.selectedItems():
            card = self.store.get_deleted(int(item.data(Qt.ItemDataRole.UserRole)))
            if card is not None:
                cards.append(card)
        return cards

    def _delete_cards(self, cards: list[Card]) -> int:
        deleted = 0
        for card in cards:
            if card.id is None or not self.store.delete_permanently(card.id):
                continue
            deleted += 1
            remove_card_image_if_unused(self.store, card, self.captures_dir)
        return deleted

    def _update_actions(self) -> None:
        has_selection = bool(self.card_list.selectedItems())
        self.restore_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.empty_button.setEnabled(self.store.deleted_count() > 0)

    def _show_result(self, message: str) -> None:
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(message, 3000)


def _display_time(value: str) -> str:
    try:
        deleted_at = datetime.fromisoformat(value).astimezone()
    except ValueError:
        return value or "recently"
    return deleted_at.strftime("%b %d, %H:%M")
