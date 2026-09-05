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


def snap_geometry_to_screen_edges(
    requested: QRect,
    screens: list[QRect],
    *,
    threshold: int = 16,
) -> QRect:
    if not screens or threshold < 0:
        return QRect(requested)

    def overlap_area(screen: QRect) -> int:
        overlap = requested.intersected(screen)
        return max(0, overlap.width()) * max(0, overlap.height())

    target = max(screens, key=overlap_area)
    if overlap_area(target) == 0:
        center = requested.center()

        def center_distance(screen: QRect) -> int:
            screen_center = screen.center()
            return (center.x() - screen_center.x()) ** 2 + (
                center.y() - screen_center.y()
            ) ** 2

        target = min(screens, key=center_distance)

    snapped = QRect(requested)
    if abs(requested.left() - target.left()) <= threshold:
        snapped.moveLeft(target.left())
    elif abs(requested.right() - target.right()) <= threshold:
        snapped.moveRight(target.right())
    if abs(requested.top() - target.top()) <= threshold:
        snapped.moveTop(target.top())
    elif abs(requested.bottom() - target.bottom()) <= threshold:
        snapped.moveBottom(target.bottom())
    return snapped


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


class _PinHeader(QWidget):
    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class PinWidget(QWidget):
    COLLAPSED_HEIGHT = 48

    def __init__(
        self,
        card: Card,
        on_layout_changed: Callable[[Card], None],
        on_unpin: Callable[[Card], None],
        on_delete: Callable[[Card], None],
        on_edit: Callable[[Card], None],
        on_lock_changed: Callable[[Card], None],
        on_collapsed_changed: Callable[[Card], None],
        on_annotate: Callable[[Card], None],
        on_copy: Callable[[Card], None],
        on_extract_text: Callable[[Card], None],
        on_copy_text: Callable[[Card], None],
        on_open_location: Callable[[Card], None],
    ) -> None:
        super().__init__()
        self.card = card
        self._temporary_opacity: float | None = None
        self._on_layout_changed = on_layout_changed
        self._on_unpin = on_unpin
        self._on_delete = on_delete
        self._on_edit = on_edit
        self._on_lock_changed = on_lock_changed
        self._on_collapsed_changed = on_collapsed_changed
        self._on_annotate = on_annotate
        self._on_copy = on_copy
        self._on_extract_text = on_extract_text
        self._on_copy_text = on_copy_text
        self._on_open_location = on_open_location
        self._drag_origin: QPoint | None = None
        self._drag_moved = False
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
        self.set_locked(card.locked, notify=False)
        self.set_collapsed(card.collapsed, notify=False)

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
            QLabel#pinLock {
                color: #ffd76d; background: #352c1c; border: 1px solid #725d2e;
                border-radius: 5px; padding: 2px 5px; font-size: 9px; font-weight: 700;
            }
            QPushButton#pinCollapse {
                color: #d5caff; background: #211b31; border: 1px solid #4b3d70;
                border-radius: 5px; font-size: 14px; font-weight: 700;
            }
            QPushButton#pinCollapse:hover { background: #302546; }
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

        self._header = _PinHeader()
        self._header.double_clicked.connect(self.toggle_collapsed)
        header = QHBoxLayout(self._header)
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel(self.card.title or "Untitled")
        title.setObjectName("pinTitle")
        game = QLabel(self.card.game or "General")
        game.setObjectName("pinGame")
        game.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._lock_indicator = QLabel("LOCKED")
        self._lock_indicator.setObjectName("pinLock")
        self._lock_indicator.setToolTip("Position and size are locked")
        self._collapse_button = QPushButton()
        self._collapse_button.setObjectName("pinCollapse")
        self._collapse_button.setFixedSize(24, 24)
        self._collapse_button.clicked.connect(self.toggle_collapsed)
        header.addWidget(title, 1)
        header.addWidget(self._lock_indicator)
        header.addWidget(game)
        header.addWidget(self._collapse_button)
        layout.addWidget(self._header)

        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        if self.card.kind is CardKind.IMAGE and Path(self.card.image_path).is_file():
            image = ScaledImage(self.card.image_path)
            image.open_requested.connect(self._open_original)
            body_layout.addWidget(image, 1)
        else:
            content = QTextBrowser()
            content.setPlainText(self.card.content)
            content.setOpenExternalLinks(True)
            body_layout.addWidget(content, 1)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)
        grip_row.addWidget(self._grip)
        body_layout.addLayout(grip_row)
        layout.addWidget(self._body, 1)

    def set_click_through(self, enabled: bool) -> None:
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        if was_visible:
            self.show()

    def set_temporary_opacity(self, opacity: float | None) -> None:
        self._temporary_opacity = (
            None if opacity is None else min(1.0, max(0.2, opacity))
        )
        self.setWindowOpacity(
            self.card.opacity if self._temporary_opacity is None else self._temporary_opacity
        )

    def contextMenuEvent(self, event: object) -> None:
        menu = QMenu(self)
        collapse = QAction("Expand pin" if self.card.collapsed else "Collapse pin", menu)
        collapse.triggered.connect(self.toggle_collapsed)
        menu.addAction(collapse)
        lock = QAction("Unlock pin" if self.card.locked else "Lock pin position", menu)
        lock.triggered.connect(lambda: self.set_locked(not self.card.locked))
        menu.addAction(lock)
        menu.addSeparator()
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
            extract_text = QAction("Extract text…", menu)
            extract_text.triggered.connect(lambda: self._on_extract_text(self.card))
            menu.addAction(extract_text)
            if self.card.content.strip():
                copy_text = QAction("Copy extracted text", menu)
                copy_text.triggered.connect(lambda: self._on_copy_text(self.card))
                menu.addAction(copy_text)
            annotate = QAction("Annotate image…", menu)
            annotate.triggered.connect(lambda: self._on_annotate(self.card))
            menu.addAction(annotate)
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

    def set_locked(self, locked: bool, *, notify: bool = True) -> None:
        self.card.locked = locked
        self._drag_origin = None
        self._drag_moved = False
        self._lock_indicator.setVisible(locked)
        self._sync_resize_grip()
        if notify:
            self._on_lock_changed(self.card)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self.card.collapsed)

    def set_collapsed(self, collapsed: bool, *, notify: bool = True) -> None:
        if collapsed and not self.card.collapsed:
            self.save_now()
        self.card.collapsed = collapsed
        self._drag_origin = None
        self._drag_moved = False
        self._body.setVisible(not collapsed)
        if collapsed:
            self.setMinimumHeight(self.COLLAPSED_HEIGHT)
            self.setMaximumHeight(self.COLLAPSED_HEIGHT)
            self.resize(self.width(), self.COLLAPSED_HEIGHT)
            self._collapse_button.setText("+")
            self._collapse_button.setToolTip("Expand pin")
        else:
            self.setMaximumHeight(16_777_215)
            self.setMinimumHeight(110)
            screens = [screen.availableGeometry() for screen in QGuiApplication.screens()]
            primary_screen = QGuiApplication.primaryScreen()
            primary_geometry = primary_screen.availableGeometry() if primary_screen else None
            expanded = fit_geometry_to_screens(
                QRect(self.x(), self.y(), self.width(), max(110, self.card.height)),
                screens,
                primary_geometry,
            )
            self.setGeometry(expanded)
            self._collapse_button.setText("−")
            self._collapse_button.setToolTip("Collapse pin")
        self._sync_resize_grip()
        self._queue_save()
        if notify:
            self._on_collapsed_changed(self.card)

    def _sync_resize_grip(self) -> None:
        enabled = not self.card.locked and not self.card.collapsed
        self._grip.setEnabled(enabled)
        self._grip.setVisible(enabled)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            not self.card.locked
            and event.button() == Qt.MouseButton.LeftButton
            and event.position().y() <= 45
        ):
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_moved = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            self._drag_moved = True
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        should_snap = self._drag_origin is not None and self._drag_moved
        self._drag_origin = None
        self._drag_moved = False
        if should_snap and not self.card.locked:
            self._snap_to_screen_edges()
        self._queue_save()
        super().mouseReleaseEvent(event)

    def _snap_to_screen_edges(self) -> None:
        screens = [screen.availableGeometry() for screen in QGuiApplication.screens()]
        snapped = snap_geometry_to_screen_edges(self.geometry(), screens)
        if snapped != self.geometry():
            self.setGeometry(snapped)

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
        if not self.card.collapsed:
            self.card.height = geometry.height()
        if self._temporary_opacity is None:
            self.card.opacity = self.windowOpacity()
        self._on_layout_changed(self.card)
