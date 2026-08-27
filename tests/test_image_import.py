from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QColor, QImage

from gaming_buddy.image_import import (
    ImageImportError,
    discard_duplicate_images,
    load_clipboard_image,
    load_image_file,
    local_image_paths,
    pixel_digest,
    save_imported_image,
)


def _sample_image(color: str = "#7657ff") -> QImage:
    image = QImage(12, 8, QImage.Format.Format_RGBA8888)
    image.fill(QColor(color))
    return image


def test_file_import_preserves_original_bytes(tmp_path: Path) -> None:
    source = tmp_path / "Puzzle Map.png"
    assert _sample_image().save(str(source), "PNG", 100)
    original = source.read_bytes()

    imported = load_image_file(source)
    destination = save_imported_image(imported, tmp_path / "captures")

    assert imported.title == "Puzzle Map"
    assert imported.source_name == source.name
    assert imported.suffix == ".png"
    assert (imported.image.width(), imported.image.height()) == (12, 8)
    assert destination.read_bytes() == original
    assert destination.parent == tmp_path / "captures"


def test_clipboard_image_is_saved_as_lossless_png(tmp_path: Path) -> None:
    source = _sample_image("#22cc88")
    imported = load_clipboard_image(source)
    destination = save_imported_image(imported, tmp_path)
    restored = QImage(str(destination))

    assert imported.suffix == ".png"
    assert destination.suffix == ".png"
    assert pixel_digest(restored) == pixel_digest(source)


def test_duplicate_filter_checks_saved_and_same_batch_images(tmp_path: Path) -> None:
    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    third_path = tmp_path / "third.png"
    assert _sample_image("red").save(str(first_path), "PNG")
    assert _sample_image("red").save(str(second_path), "PNG")
    assert _sample_image("blue").save(str(third_path), "PNG")
    first = load_image_file(first_path)
    second = load_image_file(second_path)
    third = load_image_file(third_path)
    clipboard_copy = load_clipboard_image(first.image)

    unique, duplicates = discard_duplicate_images(
        [first, second, third], {first.digest}
    )

    assert unique == [third]
    assert duplicates == 2
    assert clipboard_copy.digest == first.digest


def test_local_image_paths_filters_non_images_and_remote_urls(tmp_path: Path) -> None:
    image = tmp_path / "map.JPG"
    text = tmp_path / "notes.txt"
    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(image)),
            QUrl.fromLocalFile(str(text)),
            QUrl("https://example.com/image.png"),
        ]
    )

    assert local_image_paths(mime_data) == [image]


def test_invalid_or_unsupported_files_are_rejected(tmp_path: Path) -> None:
    damaged = tmp_path / "damaged.png"
    damaged.write_bytes(b"not an image")
    unsupported = tmp_path / "map.tiff"
    unsupported.write_bytes(b"data")

    with pytest.raises(ImageImportError, match="damaged or unreadable"):
        load_image_file(damaged)
    with pytest.raises(ImageImportError, match="Unsupported image format"):
        load_image_file(unsupported)
