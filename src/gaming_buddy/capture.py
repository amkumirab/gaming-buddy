from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    """A screen image at native pixel resolution plus its logical desktop geometry."""

    logical_geometry: QRect
    image: QImage

    @property
    def scale_x(self) -> float:
        return self.image.width() / self.logical_geometry.width()

    @property
    def scale_y(self) -> float:
        return self.image.height() / self.logical_geometry.height()


@dataclass(frozen=True, slots=True)
class DesktopSnapshot:
    preview: QImage
    virtual_geometry: QRect
    screens: tuple[ScreenCapture, ...]

    def _intersecting_screens(self, selection: QRect) -> list[ScreenCapture]:
        return [
            screen
            for screen in self.screens
            if not selection.intersected(screen.logical_geometry).isEmpty()
        ]

    def native_size(self, selection: QRect) -> QSize:
        selection = selection.intersected(self.virtual_geometry)
        screens = self._intersecting_screens(selection)
        if selection.isEmpty() or not screens:
            return QSize()
        target_scale = max(max(screen.scale_x, screen.scale_y) for screen in screens)
        return QSize(
            max(1, round(selection.width() * target_scale)),
            max(1, round(selection.height() * target_scale)),
        )

    def crop_native(self, selection: QRect) -> QImage:
        """Compose a crop without reducing high-DPI screenshots to logical pixels."""
        selection = selection.intersected(self.virtual_geometry)
        screens = self._intersecting_screens(selection)
        output_size = self.native_size(selection)
        if output_size.isEmpty() or not screens:
            return QImage()

        target_scale_x = output_size.width() / selection.width()
        target_scale_y = output_size.height() / selection.height()
        output = QImage(output_size, QImage.Format.Format_RGBA8888)
        output.fill(Qt.GlobalColor.transparent)
        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        for screen in screens:
            overlap = selection.intersected(screen.logical_geometry)
            source = QRectF(
                (overlap.x() - screen.logical_geometry.x()) * screen.scale_x,
                (overlap.y() - screen.logical_geometry.y()) * screen.scale_y,
                overlap.width() * screen.scale_x,
                overlap.height() * screen.scale_y,
            )
            target = QRectF(
                (overlap.x() - selection.x()) * target_scale_x,
                (overlap.y() - selection.y()) * target_scale_y,
                overlap.width() * target_scale_x,
                overlap.height() * target_scale_y,
            )
            painter.drawImage(target, screen.image, source)

        painter.end()
        return output


def grab_virtual_desktop() -> DesktopSnapshot:
    screens = QGuiApplication.screens()
    if not screens:
        raise RuntimeError("No display is available")

    virtual = screens[0].geometry()
    for screen in screens[1:]:
        virtual = virtual.united(screen.geometry())

    preview = QImage(virtual.size(), QImage.Format.Format_RGBA8888)
    preview.fill(Qt.GlobalColor.black)
    painter = QPainter(preview)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    captures: list[ScreenCapture] = []

    for screen in screens:
        native_image = screen.grabWindow(0).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        native_image.setDevicePixelRatio(1.0)
        geometry = screen.geometry()
        captures.append(ScreenCapture(QRect(geometry), native_image))
        preview_target = QRect(geometry.topLeft() - virtual.topLeft(), geometry.size())
        painter.drawImage(QRectF(preview_target), native_image, QRectF(native_image.rect()))

    painter.end()
    return DesktopSnapshot(preview, virtual, tuple(captures))


class SelectionOverlay(QWidget):
    selected = Signal(QImage)
    cancelled = Signal()

    def __init__(self, snapshot: DesktopSnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(snapshot.virtual_geometry)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def selection(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def _global_selection(self, selection: QRect) -> QRect:
        global_selection = QRect(selection)
        global_selection.translate(self._snapshot.virtual_geometry.topLeft())
        return global_selection

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event: object) -> None:
        del event
        painter = QPainter(self)
        painter.drawImage(0, 0, self._snapshot.preview)
        painter.fillRect(self.rect(), QColor(5, 3, 12, 155))

        selected = self.selection
        if not selected.isEmpty():
            painter.drawImage(QRectF(selected), self._snapshot.preview, QRectF(selected))
            painter.setPen(QPen(QColor("#9b84ff"), 2))
            painter.drawRect(selected.adjusted(0, 0, -1, -1))
            native = self._snapshot.native_size(self._global_selection(selected))
            label = f"{native.width()} × {native.height()} px"
            label_rect = QRect(selected.left(), max(8, selected.top() - 30), 165, 24)
            painter.fillRect(label_rect, QColor(18, 16, 27, 225))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(label_rect.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            self.rect().adjusted(0, 24, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Drag to capture at native resolution  •  Esc to cancel",
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = event.position().toPoint()
        selected = self.selection.intersected(self.rect())
        if selected.width() >= 12 and selected.height() >= 12:
            crop = self._snapshot.crop_native(self._global_selection(selected))
            if not crop.isNull():
                self.selected.emit(crop)
                self.close()
                return
        self._origin = None
        self._current = None
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)


def begin_capture(parent: QWidget | None = None) -> SelectionOverlay:
    QApplication.processEvents()
    overlay = SelectionOverlay(grab_virtual_desktop())
    if parent is not None:
        overlay.destroyed.connect(parent.show)
    overlay.show()
    return overlay
