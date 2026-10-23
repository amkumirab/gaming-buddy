"""Read-only card-pack preview with cooperative background work."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.card_pack import MAX_GAME_LENGTH, CardPack, CardPackError, load_card_pack
from gaming_buddy.card_pack_import import CardImportPlan, plan_card_import
from gaming_buddy.models import Card


class _ImagePreview(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._source = QPixmap()
        self.setMinimumSize(1, 1)
        self.setMaximumHeight(180)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_image(self, data: bytes) -> None:
        self._source = QPixmap.fromImage(QImage.fromData(data)) if data else QPixmap()
        self._fit()

    def _fit(self) -> None:
        self.setPixmap(self._source.scaled(
            max(1, self.width()), 180, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ) if not self._source.isNull() else QPixmap())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit()


class CardPackDialog(QDialog):
    work_finished = Signal()

    def __init__(
        self, source: Path, existing_cards: list[Card], captures_dir: Path,
        games: list[str], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import card pack")
        self.setModal(True)
        self.resize(620, 720)
        self.setMinimumSize(430, 560)
        self.plan: CardImportPlan | None = None
        self._pack: CardPack | None = None
        self._existing = existing_cards
        self._captures = captures_dir
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._results: queue.SimpleQueue[tuple[CardPack | CardImportPlan | None, str | None]] = queue.SimpleQueue()
        self._closing = False
        self._shutting_down = False
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "Preview shared notes and screenshots before adding them to your library. "
            "Existing cards are never overwritten; imported cards start unpinned."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.status = QLabel("Reading card pack…")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Card import status")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setAccessibleName("Reading card pack")
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.select_button = QPushButton("Select all")
        self.clear_button = QPushButton("Clear selection")
        for button in (self.select_button, self.clear_button):
            button.setAccessibleName(button.text())
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.card_list = QListWidget()
        self.card_list.setAccessibleName("Cards in shared pack")
        self.card_list.setAccessibleDescription(
            "Use Space to include or exclude a card. Select a row to preview it. "
            "Cards with missing images cannot be imported."
        )
        self.card_list.setMinimumHeight(100)
        layout.addWidget(self.card_list, 1)
        self.preview_title = QLabel("Select a card to preview")
        self.preview_title.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_title.setWordWrap(True)
        layout.addWidget(self.preview_title)
        self.image_preview = _ImagePreview()
        self.image_preview.setAccessibleName("Card image preview")
        self.image_preview.hide()
        layout.addWidget(self.image_preview)
        self.note_preview = QPlainTextEdit()
        self.note_preview.setReadOnly(True)
        self.note_preview.setAccessibleName("Card text preview")
        self.note_preview.setMinimumHeight(80)
        layout.addWidget(self.note_preview, 1)
        self.use_game = QCheckBox("Use one game for selected cards")
        self.use_game.setToolTip("Leave off to preserve each card's original game.")
        layout.addWidget(self.use_game)
        self.game_input = QComboBox()
        self.game_input.setEditable(True)
        self.game_input.addItems(games)
        self.game_input.setCurrentText("")
        self.game_input.lineEdit().setMaxLength(MAX_GAME_LENGTH)
        self.game_input.lineEdit().setPlaceholderText("Game name · blank for General")
        self.game_input.setAccessibleName("Destination game")
        layout.addWidget(self.game_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.import_button = buttons.addButton("Import selected", QDialogButtonBox.ButtonRole.AcceptRole)
        self.import_button.setAccessibleName("Import selected cards")
        self.import_button.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.select_button.clicked.connect(lambda: self._select_all(True))
        self.clear_button.clicked.connect(lambda: self._select_all(False))
        self.card_list.currentRowChanged.connect(self._preview)
        self.card_list.itemChanged.connect(self._selection_changed)
        self.use_game.toggled.connect(self._selection_changed)
        self._poller = QTimer(self)
        self._poller.setInterval(25)
        self._poller.timeout.connect(self._poll)
        self._autostart = QTimer(self)
        self._autostart.setSingleShot(True)
        self._autostart.timeout.connect(lambda: self._start(
            lambda: load_card_pack(source, cancelled=self._cancel.is_set)
        ))
        self._set_busy(True)
        self._autostart.start(0)

    @property
    def shutdown_ready(self) -> bool:
        return self._thread is None or not self._thread.is_alive()

    @property
    def missing_image_count(self) -> int:
        return sum(not card.available for card in self._pack.cards) if self._pack else 0

    def begin_shutdown(self) -> None:
        self._shutting_down = True
        self.reject()

    def _start(self, operation: Callable[[], CardPack | CardImportPlan]) -> None:
        if self._closing or self._shutting_down or self._thread is not None:
            return
        self._set_busy(True)
        results = self._results

        def run() -> None:
            result, message = None, "Could not read the card pack."
            try:
                result, message = operation(), None
            except (ValueError, OSError, RuntimeError) as error:
                # Transfer errors as data; only the GUI thread may touch widgets.
                message = str(error) if isinstance(error, CardPackError) else "Could not read the card pack."
            finally:
                results.put((result, message))

        self._thread = threading.Thread(target=run, name="card-pack-reader", daemon=True)
        try:
            self._thread.start()
        except RuntimeError:
            self._thread = None
            self._set_busy(False)
            self.status.setText("The card reader could not start. Close this dialog and try again.")
            return
        self._poller.start()

    def _poll(self) -> None:
        if self._thread is None or self._thread.is_alive():
            return
        self._thread.join()
        self._thread = None
        self._poller.stop()
        result, error = self._results.get_nowait()
        if self._closing or self._shutting_down:
            super().reject()
        elif error is not None:
            self._set_busy(False)
            self.status.setText(error)
        elif isinstance(result, CardImportPlan):
            self.plan = result
            super().accept()
        else:
            self._pack = result
            self._populate()
        self.work_finished.emit()

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        ready = not busy and self._pack is not None and not self._closing
        for widget in (self.card_list, self.select_button, self.clear_button, self.use_game):
            widget.setEnabled(ready)
        self.game_input.setEnabled(ready and self.use_game.isChecked())
        self.import_button.setEnabled(ready and bool(self.selected_indices()))

    def _populate(self) -> None:
        for card in self._pack.cards:
            label = f"{card.title} — {card.game or 'General'}"
            if not card.available:
                label += " · Image missing"
            item = QListWidgetItem(label)
            if card.available:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            self.card_list.addItem(item)
        self.card_list.setCurrentRow(0)
        self._set_busy(False)
        self._selection_changed()

    def selected_indices(self) -> list[int]:
        return [index for index in range(self.card_list.count())
                if self.card_list.item(index).checkState() == Qt.CheckState.Checked]

    def _selection_changed(self) -> None:
        if self._thread is not None or self._closing:
            return
        self._set_busy(False)
        if self._pack is not None:
            self.status.setText(
                f"{len(self.selected_indices())} of {len(self._pack.cards)} selected · "
                f"{self.missing_image_count} missing image(s). Exact duplicates will be skipped."
            )

    def _select_all(self, checked: bool) -> None:
        for index in range(self.card_list.count()):
            item = self.card_list.item(index)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _preview(self, index: int) -> None:
        if self._pack is None or not 0 <= index < len(self._pack.cards):
            return
        card = self._pack.cards[index]
        self.preview_title.setText(card.title)
        self.note_preview.setPlainText(card.content)
        self.image_preview.set_image(b"")
        self.image_preview.setVisible(card.image is not None)
        if card.image is not None:
            self.image_preview.set_image(card.image.preview or card.image.data)

    def accept(self) -> None:
        if (self._closing or self._shutting_down or self._pack is None
                or self._thread is not None or not self.selected_indices()):
            return
        pack, indices = self._pack, self.selected_indices()
        game = self.game_input.currentText() if self.use_game.isChecked() else None
        self.status.setText("Checking selected cards for duplicates…")
        self._start(lambda: plan_card_import(
            pack, indices, self._existing, self._captures,
            game=game, cancelled=self._cancel.is_set,
        ))

    def reject(self) -> None:
        self._autostart.stop()
        self._closing = True
        self._cancel.set()
        if self._thread is not None:
            self.status.setText("Cancelling… Waiting for the reader to finish.")
            self._set_busy(True)
        else:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.reject()
        event.setAccepted(self._thread is None)
