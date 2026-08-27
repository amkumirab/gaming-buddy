from __future__ import annotations

import hashlib
import struct
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QMimeData
from PySide6.QtGui import QImage

SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".webp"})
MAX_IMAGE_FILE_SIZE = 100 * 1024 * 1024


class ImageImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ImageImport:
    title: str
    source_name: str
    suffix: str
    data: bytes
    image: QImage
    digest: str


def load_image_file(path: Path) -> ImageImport:
    path = path.resolve()
    if not path.is_file():
        raise ImageImportError(f"File not found: {path.name}")
    suffix = path.suffix.casefold()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise ImageImportError(f"Unsupported image format: {path.suffix or path.name}")
    size = path.stat().st_size
    if size <= 0:
        raise ImageImportError(f"The image file is empty: {path.name}")
    if size > MAX_IMAGE_FILE_SIZE:
        raise ImageImportError(f"The image is larger than 100 MB: {path.name}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ImageImportError(f"Could not read: {path.name}") from exc
    image = QImage.fromData(data)
    if image.isNull():
        raise ImageImportError(f"The image is damaged or unreadable: {path.name}")
    return ImageImport(
        title=path.stem[:80] or "Imported image",
        source_name=path.name,
        suffix=suffix,
        data=data,
        image=image,
        digest=pixel_digest(image),
    )


def load_clipboard_image(image: QImage) -> ImageImport:
    if image.isNull():
        raise ImageImportError("The clipboard does not contain a readable image.")
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG", 100):
        raise ImageImportError("The clipboard image could not be prepared.")
    data = bytes(buffer.data())
    return ImageImport(
        title="Clipboard image",
        source_name="Clipboard image",
        suffix=".png",
        data=data,
        image=QImage(image),
        digest=pixel_digest(image),
    )


def pixel_digest(image: QImage) -> str:
    normalized = image.convertToFormat(QImage.Format.Format_RGBA8888)
    digest = hashlib.sha256()
    digest.update(struct.pack(">II", normalized.width(), normalized.height()))
    digest.update(bytes(normalized.constBits()))
    return digest.hexdigest()


def image_file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    image = QImage(str(path))
    return None if image.isNull() else pixel_digest(image)


def save_imported_image(imported: ImageImport, captures_dir: Path) -> Path:
    captures_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")
    destination = captures_dir / f"import-{timestamp}-{uuid.uuid4().hex[:10]}{imported.suffix}"
    try:
        with destination.open("xb") as output:
            output.write(imported.data)
    except OSError as exc:
        raise ImageImportError("The image could not be saved to the capture library.") from exc
    return destination


def discard_duplicate_images(
    imported: list[ImageImport], known_digests: set[str]
) -> tuple[list[ImageImport], int]:
    unique: list[ImageImport] = []
    duplicates = 0
    seen = set(known_digests)
    for candidate in imported:
        if candidate.digest in seen:
            duplicates += 1
            continue
        seen.add(candidate.digest)
        unique.append(candidate)
    return unique, duplicates


def local_image_paths(mime_data: QMimeData) -> list[Path]:
    paths: list[Path] = []
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        if path.suffix.casefold() in SUPPORTED_IMAGE_SUFFIXES:
            paths.append(path)
    return paths
