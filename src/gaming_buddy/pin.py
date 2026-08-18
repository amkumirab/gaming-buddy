from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizeGrip,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.models import Card, CardKind


class ScaledImage(QLabel):
    def __init__(self, path: str) -> None:
        super().__init__()
        self._source = QPixmap(path)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(120, 70)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        if not self._source.isNull():
            self.setPixmap(
                self._source.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


class PinWidget(QWidget):
    def __init__(
        self,
        card: Card,
        on_layout_changed: Callable[[Card], None],
        on_delete: Callable[[Card], None],
    ) -> None:
        super().__init__()
        self.card = card
        self._on_layout_changed = on_layout_changed
        self._on_delete = on_delete
        self._drag_origin: QPoint | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save_layout)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(180, 110)
        self.setGeometry(card.x, card.y, card.width, card.height)
        self.setWindowOpacity(card.opacity)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("pinFrame")
        frame.setStyleSheet(
            """
            QFrame#pinFrame {
                background: #14111deF;
                border: 1px solid #735dbe;
                border-radius: 12px;
            }
            QLabel#pinTitle { color: #d5caff; font-weight: 700; font-size: 12px; }
            QLabel#pinGame { color: #8e83a8; font-size: 10px; }
            QTextBrowser {
                background: transparent; border: none; color: #ffffff;
                padding: 5px; font-size: 14px;
            }
            """
        )
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(self.card.title or "Untitled")
        title.setObjectName("pinTitle")
        game = QLabel(self.card.game or "General")
        game.setObjectName("pinGame")
        game.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(title, 1)
        header.addWidget(game)
        layout.addLayout(header)

        if self.card.kind is CardKind.IMAGE and Path(self.card.image_path).is_file():
            layout.addWidget(ScaledImage(self.card.image_path), 1)
        else:
            content = QTextBrowser()
            content.setPlainText(self.card.content)
            content.setOpenExternalLinks(True)
            layout.addWidget(content, 1)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        grip_row.addWidget(grip)
        layout.addLayout(grip_row)

    def set_click_through(self, enabled: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        self.show()

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        for label, value in (("40%", 0.4), ("60%", 0.6), ("80%", 0.8), ("100%", 1.0)):
            action = QAction(f"Opacity {label}", menu)
            action.triggered.connect(
                lambda checked=False, opacity=value: self._set_opacity(opacity)
            )
            menu.addAction(action)
        menu.addSeparator()
        remove = QAction("Delete card", menu)
        remove.triggered.connect(lambda: self._on_delete(self.card))
        menu.addAction(remove)
        menu.exec(event.globalPos())  # type: ignore[attr-defined]

    def _set_opacity(self, opacity: float) -> None:
        self.card.opacity = opacity
        self.setWindowOpacity(opacity)
        self._queue_save()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 45:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_origin = None
        self._queue_save()
        super().mouseReleaseEvent(event)

    def moveEvent(self, event: object) -> None:
        super().moveEvent(event)  # type: ignore[arg-type]
        self._queue_save()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._queue_save()

    def _queue_save(self) -> None:
        if self.card.id is not None:
            self._save_timer.start()

    def _save_layout(self) -> None:
        geometry = self.geometry()
        self.card.x = geometry.x()
        self.card.y = geometry.y()
        self.card.width = geometry.width()
        self.card.height = geometry.height()
        self.card.opacity = self.windowOpacity()
        self._on_layout_changed(self.card)
