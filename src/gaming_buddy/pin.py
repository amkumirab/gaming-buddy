from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QGuiApplication,
    QMouseEvent,
    QPixmap,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.models import Card, CardKind


def fit_geometry_to_screens(
    requested: QRect,
    screens: list[QRect],
    primary: QRect | None = None,
) -> QRect:
    """Keep a restored pin fully visible after monitor or resolution changes."""
    if not screens:
        return QRect(requested)
    target_primary = primary if primary in screens else screens[0]

    def overlap_area(screen: QRect) -> int:
        overlap = requested.intersected(screen)
        return max(0, overlap.width()) * max(0, overlap.height())

    target = max(screens, key=overlap_area)
    if overlap_area(target) == 0:
        target = target_primary

    width = min(max(180, requested.width()), target.width())
    height = min(max(110, requested.height()), target.height())
    maximum_x = target.x() + target.width() - width
    maximum_y = target.y() + target.height() - height
    x = max(target.x(), min(requested.x(), maximum_x))
    y = max(target.y(), min(requested.y(), maximum_y))
    return QRect(x, y, width, height)


class FullImageViewer(QDialog):
    """Always-on-top viewer that can display the original screenshot pixel-for-pixel."""

    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = QPixmap(path)
        self._scale = 1.0
        self._fit_mode = True
        self.setObjectName("imageViewer")
        self.setWindowTitle(f"Screenshot · {self._source.width()} × {self._source.height()} px")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(560, 420)
        self.resize(960, 700)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        fit_button = QPushButton("Fit")
        fit_button.clicked.connect(self.fit_to_window)
        actual_button = QPushButton("100%")
        actual_button.clicked.connect(self.show_actual_size)
        zoom_out = QPushButton("−")
        zoom_out.setFixedWidth(42)
        zoom_out.clicked.connect(lambda: self.zoom_by(0.8))
        zoom_in = QPushButton("+")
        zoom_in.setFixedWidth(42)
        zoom_in.clicked.connect(lambda: self.zoom_by(1.25))
        self.info = QLabel()
        self.info.setObjectName("muted")
        toolbar.addWidget(fit_button)
        toolbar.addWidget(actual_button)
        toolbar.addWidget(zoom_out)
        toolbar.addWidget(zoom_in)
        toolbar.addStretch(1)
        toolbar.addWidget(self.info)
        layout.addLayout(toolbar)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setStyleSheet("background: #08070d;")
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.image)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setStyleSheet("QScrollArea { background: #08070d; border: none; }")
        layout.addWidget(self.scroll, 1)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_to_window)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            QTimer.singleShot(0, self.fit_to_window)

    def fit_to_window(self) -> None:
        if self._source.isNull():
            return
        viewport = self.scroll.viewport().size()
        available_width = max(1, viewport.width() - 8)
        available_height = max(1, viewport.height() - 8)
        self._scale = min(
            1.0,
            available_width / self._source.width(),
            available_height / self._source.height(),
        )
        self._fit_mode = True
        self._render()

    def show_actual_size(self) -> None:
        self._scale = 1.0
        self._fit_mode = False
        self._render()

    def zoom_by(self, factor: float) -> None:
        self._scale = max(0.1, min(4.0, self._scale * factor))
        self._fit_mode = False
        self._render()

    def _render(self) -> None:
        if self._source.isNull():
            return
        if abs(self._scale - 1.0) < 0.001:
            rendered = self._source
        else:
            rendered = self._source.scaled(
                max(1, round(self._source.width() * self._scale)),
                max(1, round(self._source.height() * self._scale)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.image.setPixmap(rendered)
        self.image.resize(rendered.size())
        self.info.setText(
            f"{self._source.width()} × {self._source.height()} px  ·  {self._scale:.0%}"
        )


class ScaledImage(QLabel):
    open_requested = Signal()

    def __init__(self, path: str) -> None:
        super().__init__()
        self._source = QPixmap(path)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(120, 70)
        self.setToolTip("Double-click to view the original resolution")

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

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class PinWidget(QWidget):
    def __init__(
        self,
        card: Card,
        on_layout_changed: Callable[[Card], None],
        on_unpin: Callable[[Card], None],
        on_delete: Callable[[Card], None],
        on_edit: Callable[[Card], None],
        on_copy: Callable[[Card], None],
        on_open_location: Callable[[Card], None],
    ) -> None:
        super().__init__()
        self.card = card
        self._on_layout_changed = on_layout_changed
        self._on_unpin = on_unpin
        self._on_delete = on_delete
        self._on_edit = on_edit
        self._on_copy = on_copy
        self._on_open_location = on_open_location
        self._drag_origin: QPoint | None = None
        self._viewer: FullImageViewer | None = None
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
        screen_geometries = [screen.availableGeometry() for screen in QGuiApplication.screens()]
        primary_screen = QGuiApplication.primaryScreen()
        primary_geometry = primary_screen.availableGeometry() if primary_screen else None
        geometry = fit_geometry_to_screens(
            QRect(card.x, card.y, card.width, card.height),
            screen_geometries,
            primary_geometry,
        )
        card.x, card.y = geometry.x(), geometry.y()
        card.width, card.height = geometry.width(), geometry.height()
        self.setGeometry(geometry)
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
            image = ScaledImage(self.card.image_path)
            image.open_requested.connect(self._open_original)
            layout.addWidget(image, 1)
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
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        if was_visible:
            self.show()

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        edit = QAction("Edit card…", menu)
        edit.triggered.connect(lambda: self._on_edit(self.card))
        menu.addAction(edit)
        copy = QAction(
            "Copy image" if self.card.kind is CardKind.IMAGE else "Copy note text",
            menu,
        )
        copy.triggered.connect(lambda: self._on_copy(self.card))
        menu.addAction(copy)
        if self.card.kind is CardKind.IMAGE:
            open_location = QAction("Open file location", menu)
            open_location.triggered.connect(lambda: self._on_open_location(self.card))
            menu.addAction(open_location)
        menu.addSeparator()
        unpin = QAction("Unpin card", menu)
        unpin.triggered.connect(lambda: self._on_unpin(self.card))
        menu.addAction(unpin)
        menu.addSeparator()
        if self.card.kind is CardKind.IMAGE and Path(self.card.image_path).is_file():
            view = QAction("View original resolution", menu)
            view.triggered.connect(self._open_original)
            menu.addAction(view)
            menu.addSeparator()
        for label, value in (("40%", 0.4), ("60%", 0.6), ("80%", 0.8), ("100%", 1.0)):
            action = QAction(f"Opacity {label}", menu)
            action.triggered.connect(
                lambda checked=False, opacity=value: self._set_opacity(opacity)
            )
            menu.addAction(action)
        menu.addSeparator()
        remove = QAction("Move to trash", menu)
        remove.triggered.connect(lambda: self._on_delete(self.card))
        menu.addAction(remove)
        menu.exec(event.globalPos())  # type: ignore[attr-defined]

    def _open_original(self) -> None:
        if not Path(self.card.image_path).is_file():
            return
        self._viewer = FullImageViewer(self.card.image_path, self)
        self._viewer.show()
        self._viewer.raise_()

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

    def save_now(self) -> None:
        self._save_timer.stop()
        self._save_layout()

    def _save_layout(self) -> None:
        geometry = self.geometry()
        self.card.x = geometry.x()
        self.card.y = geometry.y()
        self.card.width = geometry.width()
        self.card.height = geometry.height()
        self.card.opacity = self.windowOpacity()
        self._on_layout_changed(self.card)
