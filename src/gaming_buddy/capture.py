from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget


def grab_virtual_desktop() -> tuple[QPixmap, QRect]:
    screens = QGuiApplication.screens()
    if not screens:
        raise RuntimeError("No display is available")

    virtual = screens[0].geometry()
    for screen in screens[1:]:
        virtual = virtual.united(screen.geometry())

    canvas = QPixmap(virtual.size())
    canvas.fill(Qt.GlobalColor.black)
    painter = QPainter(canvas)
    for screen in screens:
        shot = screen.grabWindow(0)
        offset = screen.geometry().topLeft() - virtual.topLeft()
        painter.drawPixmap(offset, shot)
    painter.end()
    return canvas, virtual


class SelectionOverlay(QWidget):
    selected = Signal(QPixmap)
    cancelled = Signal()

    def __init__(self, desktop: QPixmap, virtual_geometry: QRect) -> None:
        super().__init__()
        self._desktop = desktop
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(virtual_geometry)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def selection(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event: object) -> None:
        del event
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._desktop)
        painter.fillRect(self.rect(), QColor(5, 3, 12, 155))

        selected = self.selection
        if not selected.isEmpty():
            painter.drawPixmap(selected, self._desktop, selected)
            painter.setPen(QPen(QColor("#9b84ff"), 2))
            painter.drawRect(selected.adjusted(0, 0, -1, -1))
            label = f"{selected.width()} × {selected.height()}"
            label_rect = QRect(selected.left(), max(8, selected.top() - 30), 120, 24)
            painter.fillRect(label_rect, QColor(18, 16, 27, 225))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(label_rect.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            self.rect().adjusted(0, 24, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Drag to capture  •  Esc to cancel",
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
            crop = self._desktop.copy(selected)
            self.selected.emit(crop)
            self.close()
        else:
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
    desktop, geometry = grab_virtual_desktop()
    overlay = SelectionOverlay(desktop, geometry)
    if parent is not None:
        overlay.destroyed.connect(parent.show)
    overlay.show()
    return overlay
