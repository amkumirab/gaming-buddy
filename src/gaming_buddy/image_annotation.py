from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AnnotationSaveError(OSError):
    pass


class AnnotationTool(StrEnum):
    PEN = "pen"
    ARROW = "arrow"
    RECTANGLE = "rectangle"
    TEXT = "text"
    ERASER = "eraser"


class AnnotationDocument:
    def __init__(self, image: QImage, history_limit: int = 30) -> None:
        if image.isNull():
            raise ValueError("A readable image is required.")
        self.original = image.convertToFormat(QImage.Format.Format_ARGB32)
        self.image = self.original.copy()
        self.history_limit = max(1, history_limit)
        self._undo: list[QImage] = []
        self._redo: list[QImage] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def has_changes(self) -> bool:
        return self.image != self.original

    def add_pen(self, points: list[QPointF], color: QColor, width: int) -> bool:
        return self._apply(lambda image: _draw_pen(image, points, color, width))

    def add_arrow(self, start: QPointF, end: QPointF, color: QColor, width: int) -> bool:
        if _distance(start, end) < 2:
            return False
        return self._apply(lambda image: _draw_arrow(image, start, end, color, width))

    def add_rectangle(
        self, start: QPointF, end: QPointF, color: QColor, width: int
    ) -> bool:
        if _distance(start, end) < 2:
            return False
        return self._apply(lambda image: _draw_rectangle(image, start, end, color, width))

    def add_text(self, position: QPointF, text: str, color: QColor, width: int) -> bool:
        text = text.strip()
        if not text:
            return False
        return self._apply(lambda image: _draw_text(image, position, text, color, width))

    def erase(self, points: list[QPointF], width: int) -> bool:
        return self._apply(
            lambda image: _restore_original(image, self.original, points, max(12, width * 4))
        )

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.image.copy())
        self.image = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.image.copy())
        self.image = self._redo.pop()
        return True

    def reset(self) -> bool:
        if not self.has_changes:
            return False
        self._remember_current()
        self.image = self.original.copy()
        self._redo.clear()
        return True

    def preview(
        self,
        tool: AnnotationTool,
        points: list[QPointF],
        color: QColor,
        width: int,
    ) -> QImage:
        preview = self.image.copy()
        if tool is AnnotationTool.PEN:
            _draw_pen(preview, points, color, width)
        elif tool is AnnotationTool.ARROW and points:
            _draw_arrow(preview, points[0], points[-1], color, width)
        elif tool is AnnotationTool.RECTANGLE and points:
            _draw_rectangle(preview, points[0], points[-1], color, width)
        elif tool is AnnotationTool.ERASER:
            _restore_original(preview, self.original, points, max(12, width * 4))
        return preview

    def _apply(self, draw: Callable[[QImage], None]) -> bool:
        before = self.image.copy()
        updated = self.image.copy()
        draw(updated)
        if updated == self.image:
            return False
        self._undo.append(before)
        if len(self._undo) > self.history_limit:
            self._undo.pop(0)
        self.image = updated
        self._redo.clear()
        return True

    def _remember_current(self) -> None:
        self._undo.append(self.image.copy())
        if len(self._undo) > self.history_limit:
            self._undo.pop(0)


class AnnotationCanvas(QWidget):
    state_changed = Signal()

    def __init__(self, image: QImage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.document = AnnotationDocument(image)
        self.tool = AnnotationTool.PEN
        self.color = QColor("#ffcc33")
        self.width = 6
        self._gesture: list[QPointF] = []
        self.setMinimumSize(520, 360)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_tool(self, tool: AnnotationTool) -> None:
        self.tool = tool
        self._gesture.clear()
        self.update()

    def undo(self) -> None:
        if self.document.undo():
            self.state_changed.emit()
            self.update()

    def redo(self) -> None:
        if self.document.redo():
            self.state_changed.emit()
            self.update()

    def reset(self) -> None:
        if self.document.reset():
            self.state_changed.emit()
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#08070d"))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        image = (
            self.document.preview(self.tool, self._gesture, self.color, self.width)
            if self._gesture
            else self.document.image
        )
        painter.drawImage(self._image_rect(), image)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        point = self._to_image_point(event.position())
        if point is None:
            return
        self.setFocus()
        if self.tool is AnnotationTool.TEXT:
            text, accepted = QInputDialog.getText(self, "Add text", "Text")
            if accepted and self.document.add_text(point, text, self.color, self.width):
                self.state_changed.emit()
                self.update()
            return
        self._gesture = [point]
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._gesture or not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        point = self._to_image_point(event.position(), clamp=True)
        if point is not None:
            if self.tool in {AnnotationTool.PEN, AnnotationTool.ERASER}:
                self._gesture.append(point)
            else:
                self._gesture = [self._gesture[0], point]
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._gesture:
            super().mouseReleaseEvent(event)
            return
        point = self._to_image_point(event.position(), clamp=True)
        if point is not None and (len(self._gesture) == 1 or self._gesture[-1] != point):
            self._gesture.append(point)
        changed = self._commit_gesture()
        self._gesture.clear()
        if changed:
            self.state_changed.emit()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self._gesture:
            self._gesture.clear()
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def _commit_gesture(self) -> bool:
        if self.tool is AnnotationTool.PEN:
            return self.document.add_pen(self._gesture, self.color, self.width)
        if self.tool is AnnotationTool.ARROW:
            return self.document.add_arrow(
                self._gesture[0], self._gesture[-1], self.color, self.width
            )
        if self.tool is AnnotationTool.RECTANGLE:
            return self.document.add_rectangle(
                self._gesture[0], self._gesture[-1], self.color, self.width
            )
        if self.tool is AnnotationTool.ERASER:
            return self.document.erase(self._gesture, self.width)
        return False

    def _image_rect(self) -> QRectF:
        image = self.document.image
        available = self.rect().adjusted(10, 10, -10, -10)
        scale = min(available.width() / image.width(), available.height() / image.height())
        width = image.width() * scale
        height = image.height() * scale
        return QRectF(
            available.center().x() - width / 2,
            available.center().y() - height / 2,
            width,
            height,
        )

    def _to_image_point(self, position: QPointF, *, clamp: bool = False) -> QPointF | None:
        target = self._image_rect()
        if not clamp and not target.contains(position):
            return None
        x = (position.x() - target.x()) * self.document.image.width() / target.width()
        y = (position.y() - target.y()) * self.document.image.height() / target.height()
        if clamp:
            x = min(max(0.0, x), self.document.image.width() - 1.0)
            y = min(max(0.0, y), self.document.image.height() - 1.0)
        return QPointF(x, y)


class AnnotationDialog(QDialog):
    def __init__(self, image_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        source = QImage(str(image_path))
        if source.isNull():
            raise ValueError("The image could not be opened.")
        self.pin_after_save = False
        self.setWindowTitle(f"Annotate · {image_path.name}")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(840, 620)
        self.resize(1100, 780)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        tool_row = QHBoxLayout()
        self.canvas = AnnotationCanvas(source)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[AnnotationTool, QPushButton] = {}
        for tool, label in (
            (AnnotationTool.PEN, "Pen"),
            (AnnotationTool.ARROW, "Arrow"),
            (AnnotationTool.RECTANGLE, "Rectangle"),
            (AnnotationTool.TEXT, "Text"),
            (AnnotationTool.ERASER, "Eraser"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, selected=tool: self.canvas.set_tool(selected)
            )
            self.tool_group.addButton(button)
            self.tool_buttons[tool] = button
            tool_row.addWidget(button)
        self.tool_buttons[AnnotationTool.PEN].setChecked(True)

        self.color_button = QPushButton("Color")
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()
        tool_row.addWidget(self.color_button)
        self.thickness = QComboBox()
        for label, value in (("Thin", 3), ("Medium", 6), ("Thick", 12), ("Bold", 20)):
            self.thickness.addItem(label, value)
        self.thickness.setCurrentIndex(1)
        self.thickness.currentIndexChanged.connect(self._set_thickness)
        tool_row.addWidget(self.thickness)
        tool_row.addStretch(1)
        layout.addLayout(tool_row)

        history_row = QHBoxLayout()
        shortcut_hint = QLabel("Ctrl+Z undo · Ctrl+Y redo · Esc cancel stroke")
        shortcut_hint.setObjectName("muted")
        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.canvas.undo)
        self.redo_button = QPushButton("Redo")
        self.redo_button.clicked.connect(self.canvas.redo)
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.canvas.reset)
        history_row.addWidget(shortcut_hint)
        history_row.addStretch(1)
        history_row.addWidget(self.undo_button)
        history_row.addWidget(self.redo_button)
        history_row.addWidget(self.reset_button)
        layout.addLayout(history_row)
        layout.addWidget(self.canvas, 1)

        footer = QHBoxLayout()
        info = QLabel(
            f"{source.width()} × {source.height()} px · The original file stays unchanged"
        )
        info.setObjectName("muted")
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Save copy")
        self.save_button.clicked.connect(lambda: self._finish(False))
        self.pin_button = QPushButton("Save and pin")
        self.pin_button.setObjectName("primary")
        self.pin_button.clicked.connect(lambda: self._finish(True))
        footer.addWidget(info, 1)
        footer.addWidget(cancel)
        footer.addWidget(self.save_button)
        footer.addWidget(self.pin_button)
        layout.addLayout(footer)

        self.canvas.state_changed.connect(self._update_actions)
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.canvas.undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.canvas.redo)
        self._update_actions()

    @property
    def annotated_image(self) -> QImage:
        return self.canvas.document.image.copy()

    def _set_thickness(self, _index: int) -> None:
        self.canvas.width = int(self.thickness.currentData())

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self.canvas.color, self, "Annotation color")
        if color.isValid():
            self.canvas.color = color
            self._update_color_button()

    def _update_color_button(self) -> None:
        self.color_button.setStyleSheet(
            f"QPushButton {{ border: 3px solid {self.canvas.color.name()}; }}"
        )

    def _update_actions(self) -> None:
        document = self.canvas.document
        self.undo_button.setEnabled(document.can_undo)
        self.redo_button.setEnabled(document.can_redo)
        self.reset_button.setEnabled(document.has_changes)
        self.save_button.setEnabled(document.has_changes)
        self.pin_button.setEnabled(document.has_changes)

    def _finish(self, pin_after_save: bool) -> None:
        if not self.canvas.document.has_changes:
            return
        self.pin_after_save = pin_after_save
        self.accept()


def save_annotated_image(image: QImage, captures_dir: Path) -> Path:
    if image.isNull():
        raise AnnotationSaveError("The annotated image is empty.")
    captures_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")
    destination = captures_dir / f"annotated-{timestamp}-{uuid.uuid4().hex[:10]}.png"
    if not image.save(str(destination), "PNG", 100):
        destination.unlink(missing_ok=True)
        raise AnnotationSaveError("The annotated copy could not be saved.")
    return destination


def _draw_pen(image: QImage, points: list[QPointF], color: QColor, width: int) -> None:
    if not points:
        return
    painter = _annotation_painter(image, color, width)
    if len(points) == 1:
        painter.drawPoint(points[0])
    else:
        for start, end in pairwise(points):
            painter.drawLine(start, end)
    painter.end()


def _draw_arrow(
    image: QImage, start: QPointF, end: QPointF, color: QColor, width: int
) -> None:
    painter = _annotation_painter(image, color, width)
    painter.drawLine(start, end)
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    head = max(12.0, width * 3.0)
    for offset in (math.pi / 6, -math.pi / 6):
        point = QPointF(
            end.x() - math.cos(angle + offset) * head,
            end.y() - math.sin(angle + offset) * head,
        )
        painter.drawLine(end, point)
    painter.end()


def _draw_rectangle(
    image: QImage, start: QPointF, end: QPointF, color: QColor, width: int
) -> None:
    painter = _annotation_painter(image, color, width)
    painter.drawRect(QRectF(start, end).normalized())
    painter.end()


def _draw_text(
    image: QImage, position: QPointF, text: str, color: QColor, width: int
) -> None:
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont("Segoe UI")
    font.setPixelSize(max(16, width * 4))
    font.setBold(True)
    painter.setFont(font)
    metrics = QFontMetricsF(font)
    bounds = metrics.boundingRect(text)
    background = QRectF(
        position.x() - 5,
        position.y() - 4,
        bounds.width() + 10,
        bounds.height() + 8,
    )
    painter.fillRect(background, QColor(0, 0, 0, 155))
    painter.setPen(color)
    painter.drawText(QPointF(position.x(), position.y() + metrics.ascent()), text)
    painter.end()


def _restore_original(
    image: QImage, original: QImage, points: list[QPointF], diameter: int
) -> None:
    if not points:
        return
    path = QPainterPath()
    path.moveTo(points[0])
    for point in points[1:]:
        path.lineTo(point)
    if len(points) == 1:
        radius = diameter / 2
        clip_path = QPainterPath()
        clip_path.addEllipse(points[0], radius, radius)
    else:
        stroker = QPainterPathStroker()
        stroker.setWidth(diameter)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        clip_path = stroker.createStroke(path)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipPath(clip_path)
    painter.drawImage(0, 0, original)
    painter.end()


def _annotation_painter(image: QImage, color: QColor, width: int) -> QPainter:
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, max(1, width))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    return painter


def _distance(start: QPointF, end: QPointF) -> float:
    return math.hypot(end.x() - start.x(), end.y() - start.y())
