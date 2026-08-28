from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from gaming_buddy.image_annotation import (
    AnnotationDialog,
    AnnotationDocument,
    AnnotationTool,
    save_annotated_image,
)


@pytest.fixture(scope="module", autouse=True)
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _sample_image(color: str = "#f4f1ff") -> QImage:
    image = QImage(160, 100, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


def test_annotations_support_undo_redo_and_reset() -> None:
    source = _sample_image()
    document = AnnotationDocument(source)

    assert document.add_rectangle(
        QPointF(20, 20), QPointF(90, 70), QColor("#ff3366"), 6
    )
    annotated = document.image.copy()
    assert document.has_changes
    assert document.can_undo

    assert document.undo()
    assert document.image == source
    assert document.can_redo

    assert document.redo()
    assert document.image == annotated
    assert document.reset()
    assert document.image == source
    assert document.undo()
    assert document.image == annotated


def test_all_drawing_tools_change_the_full_resolution_image() -> None:
    document = AnnotationDocument(_sample_image())
    color = QColor("#7657ff")

    assert document.add_pen([QPointF(10, 10), QPointF(60, 20)], color, 4)
    assert document.add_arrow(QPointF(15, 80), QPointF(80, 45), color, 5)
    assert document.add_rectangle(QPointF(90, 10), QPointF(145, 55), color, 3)
    assert document.add_text(QPointF(20, 55), "Vault 42", color, 5)
    assert document.image.size() == document.original.size()
    assert document.has_changes


def test_eraser_restores_pixels_from_the_original() -> None:
    document = AnnotationDocument(_sample_image("#ffffff"))
    assert document.add_pen([QPointF(40, 50), QPointF(120, 50)], QColor("#000000"), 12)
    assert document.image.pixelColor(80, 50) != document.original.pixelColor(80, 50)

    assert document.erase([QPointF(40, 50), QPointF(120, 50)], 12)
    assert document.image.pixelColor(80, 50) == document.original.pixelColor(80, 50)


def test_preview_does_not_modify_document() -> None:
    document = AnnotationDocument(_sample_image())
    preview = document.preview(
        AnnotationTool.ARROW,
        [QPointF(10, 10), QPointF(100, 60)],
        QColor("#ffcc33"),
        6,
    )

    assert preview != document.image
    assert not document.has_changes
    assert not document.can_undo


def test_save_creates_lossless_copy_without_touching_source(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    source = _sample_image()
    assert source.save(str(source_path), "PNG", 100)
    original_bytes = source_path.read_bytes()
    document = AnnotationDocument(source)
    assert document.add_arrow(
        QPointF(15, 15), QPointF(120, 70), QColor("#ff3366"), 5
    )

    destination = save_annotated_image(document.image, tmp_path / "captures")
    restored = QImage(str(destination))

    assert destination.name.startswith("annotated-")
    assert destination.suffix == ".png"
    assert source_path.read_bytes() == original_bytes
    assert restored == document.image
    assert restored != source


def test_dialog_requires_a_change_before_saving(
    application: QApplication, tmp_path: Path
) -> None:
    source_path = tmp_path / "map.png"
    assert _sample_image().save(str(source_path), "PNG", 100)
    dialog = AnnotationDialog(source_path)

    assert len(dialog.tool_buttons) == 5
    assert not dialog.save_button.isEnabled()
    assert not dialog.pin_button.isEnabled()

    assert dialog.canvas.document.add_text(
        QPointF(20, 30), "Door code", QColor("#ffcc33"), 6
    )
    dialog.canvas.state_changed.emit()

    assert dialog.save_button.isEnabled()
    assert dialog.pin_button.isEnabled()
    dialog.close()
