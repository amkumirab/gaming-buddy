from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImageReader, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.models import Card, CardKind


def format_file_size(size: int) -> str:
    value = float(max(0, size))
    units = ("B", "KB", "MB", "GB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            precision = 0 if unit == "B" else 1
            return f"{value:.{precision}f} {unit}"
        value /= 1024
    return "0 B"


def format_saved_at(value: str) -> str:
    if not value:
        return "Saved date unavailable"
    try:
        saved_at = datetime.fromisoformat(value)
    except ValueError:
        return "Saved date unavailable"
    if saved_at.tzinfo is not None:
        saved_at = saved_at.astimezone()
    return f"Saved {saved_at.strftime('%d %b %Y, %H:%M')}"


def image_summary(image_path: Path) -> str:
    if not image_path.is_file():
        return "Image file missing"
    reader = QImageReader(str(image_path))
    size = reader.size()
    details: list[str] = []
    image_format = bytes(reader.format()).decode("ascii", errors="ignore").upper()
    details.append(image_format or image_path.suffix.lstrip(".").upper() or "IMAGE")
    if size.isValid():
        details.append(f"{size.width()} × {size.height()} px")
    try:
        details.append(format_file_size(image_path.stat().st_size))
    except OSError:
        pass
    return " · ".join(details)


class _ScaledPreview(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = QPixmap()
        self.setObjectName("previewImage")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(280, 180)
        self.setMaximumHeight(290)
        self.setText("Image preview unavailable")

    def set_image(self, image_path: Path) -> bool:
        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            self.clear_image("Image preview unavailable")
            return False
        self._source = QPixmap.fromImage(image)
        self.setText("")
        self._update_pixmap()
        return True

    def clear_image(self, message: str = "Image preview unavailable") -> None:
        self._source = QPixmap()
        self.setPixmap(QPixmap())
        self.setText(message)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_pixmap()

    def sizeHint(self) -> QSize:
        return QSize(340, 220)

    def _update_pixmap(self) -> None:
        if self._source.isNull() or not self.size().isValid():
            return
        self.setPixmap(
            self._source.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class CardPreviewPanel(QFrame):
    pin_requested = Signal(object)
    edit_requested = Signal(object)
    copy_requested = Signal(object)
    extract_text_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card: Card | None = None
        self.setObjectName("cardPreview")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 11)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title = QLabel("Select a card")
        self.title.setObjectName("previewTitle")
        self.title.setWordWrap(True)
        self.kind = QLabel("—")
        self.kind.setObjectName("previewBadge")
        self.kind.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.title, 1)
        header.addWidget(self.kind)
        layout.addLayout(header)

        self.image = _ScaledPreview()
        self.image.hide()
        layout.addWidget(self.image)

        self.game = QLabel("Choose a saved card to preview its contents.")
        self.game.setObjectName("previewGame")
        self.game.setWordWrap(True)
        self.metadata = QLabel("Use the arrow keys to move through the library.")
        self.metadata.setObjectName("muted")
        self.metadata.setWordWrap(True)
        self.content_heading = QLabel("CONTENTS")
        self.content_heading.setObjectName("section")
        self.content = QTextBrowser()
        self.content.setObjectName("previewText")
        self.content.setOpenExternalLinks(False)
        self.content.setMinimumHeight(140)
        self.content.hide()
        self.content_heading.hide()
        layout.addWidget(self.game)
        layout.addWidget(self.metadata)
        layout.addWidget(self.content_heading)
        layout.addWidget(self.content, 1)

        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        self.pin_button = QPushButton("Pin")
        self.pin_button.setObjectName("primary")
        self.edit_button = QPushButton("Edit")
        self.copy_button = QPushButton("Copy")
        self.extract_button = QPushButton("Extract text")
        self.pin_button.clicked.connect(self._request_pin)
        self.edit_button.clicked.connect(self._request_edit)
        self.copy_button.clicked.connect(self._request_copy)
        self.extract_button.clicked.connect(self._request_extract_text)
        actions.addWidget(self.pin_button, 0, 0)
        actions.addWidget(self.edit_button, 0, 1)
        actions.addWidget(self.copy_button, 1, 0)
        actions.addWidget(self.extract_button, 1, 1)
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        layout.addLayout(actions)

        self.clear()

    @property
    def card(self) -> Card | None:
        return self._card

    def set_card(self, card: Card) -> None:
        self._card = card
        is_image = card.kind is CardKind.IMAGE
        self.title.setText(card.title or "Untitled")
        self.kind.setText("IMAGE" if is_image else "NOTE")
        statuses = [card.game.strip() or "General"]
        if card.favorite:
            statuses.append("Favorite")
        if card.pinned:
            statuses.append("Pinned")
        self.game.setText(" · ".join(statuses))

        saved = format_saved_at(card.created_at)
        if is_image:
            image_path = Path(card.image_path)
            available = image_path.is_file()
            self.metadata.setText(f"{image_summary(image_path)} · {saved}")
            self.image.show()
            self.image.set_image(image_path)
            self.content_heading.setText("EXTRACTED TEXT")
            self.content.setPlainText(card.content.strip() or "No extracted text saved yet.")
            self.extract_button.show()
            self.extract_button.setEnabled(available)
            self.copy_button.setText("Copy image")
            self.copy_button.setEnabled(available)
        else:
            self.metadata.setText(f"Note · {saved}")
            self.image.hide()
            self.image.clear_image()
            self.content_heading.setText("NOTE")
            self.content.setPlainText(card.content)
            self.extract_button.hide()
            self.copy_button.setText("Copy note")
            self.copy_button.setEnabled(bool(card.content))

        self.content_heading.show()
        self.content.show()
        self.pin_button.setText("Show pin" if card.pinned else "Pin")
        self.pin_button.setEnabled(card.id is not None)
        self.edit_button.setEnabled(card.id is not None)

    def clear(self) -> None:
        self._card = None
        self.title.setText("Select a card")
        self.kind.setText("—")
        self.game.setText("Choose a saved card to preview its contents.")
        self.metadata.setText("Use the arrow keys to move through the library.")
        self.image.hide()
        self.image.clear_image()
        self.content_heading.hide()
        self.content.hide()
        self.extract_button.hide()
        for button in (self.pin_button, self.edit_button, self.copy_button):
            button.setEnabled(False)

    def _request_pin(self) -> None:
        if self._card is not None:
            self.pin_requested.emit(self._card)

    def _request_edit(self) -> None:
        if self._card is not None:
            self.edit_requested.emit(self._card)

    def _request_copy(self) -> None:
        if self._card is not None:
            self.copy_requested.emit(self._card)

    def _request_extract_text(self) -> None:
        if self._card is not None and self._card.kind is CardKind.IMAGE:
            self.extract_text_requested.emit(self._card)
