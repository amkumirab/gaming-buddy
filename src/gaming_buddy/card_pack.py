"""Read shared card exports without extracting or trusting archive paths."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import struct
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImageReader

from gaming_buddy.card_export import EXPORT_FORMAT, EXPORT_VERSION
from gaming_buddy.models import CardKind
from gaming_buddy.tags import MAX_TAG_LENGTH, MAX_TAGS_PER_CARD, normalize_tags

MAX_PACK_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_CARDS = 1000
MAX_MEMBERS = MAX_CARDS + 2
MAX_DIRECTORY_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 32_000_000
MAX_TOTAL_PIXELS = 64_000_000
MAX_GAME_LENGTH = 160
CancelCheck = Callable[[], bool]


class CardPackError(ValueError):
    pass


def check_cancelled(cancelled: CancelCheck | None) -> None:
    if cancelled is not None and cancelled():
        raise CardPackError("Card import cancelled.")


@dataclass(frozen=True, slots=True)
class PackImage:
    data: bytes
    suffix: str
    digest: str
    preview: bytes = b""


@dataclass(frozen=True, slots=True)
class PackCard:
    kind: CardKind
    game: str
    title: str
    content: str
    tags: tuple[str, ...]
    favorite: bool
    created_at: str
    image: PackImage | None = None

    @property
    def available(self) -> bool:
        return self.kind is CardKind.NOTE or self.image is not None


@dataclass(frozen=True, slots=True)
class CardPack:
    cards: tuple[PackCard, ...]


def _preflight_directory(data: bytes) -> None:
    # ZipFile eagerly creates every ZipInfo; check actual directory records first.
    end = data.rfind(b"PK\x05\x06", max(0, len(data) - 65_557))
    if end < 0 or end + 22 > len(data):
        raise CardPackError("This is not a supported card-pack ZIP.")
    if end >= 20 and data[end - 20:end - 16] == b"PK\x06\x07":
        raise CardPackError("ZIP64 card packs are not supported.")
    _, disk, directory_disk, count_disk, count, size, offset, comment = struct.unpack_from(
        "<4s4H2LH", data, end,
    )
    if (disk or directory_disk or count_disk != count or count > MAX_MEMBERS
            or size > MAX_DIRECTORY_BYTES or offset + size != end
            or end + 22 + comment != len(data)):
        raise CardPackError("The ZIP directory exceeds supported limits or is invalid.")
    cursor, actual = offset, 0
    while cursor < end:
        if cursor + 46 > end or data[cursor:cursor + 4] != b"PK\x01\x02":
            raise CardPackError("The ZIP directory is invalid.")
        name, extra, note = struct.unpack_from("<3H", data, cursor + 28)
        actual += 1
        if actual > MAX_MEMBERS or name > 512:
            raise CardPackError("The ZIP contains too many files or an oversized filename.")
        cursor += 46 + name + extra + note
    if cursor != end or actual != count:
        raise CardPackError("The ZIP directory count is inconsistent.")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CardPackError("Card metadata contains duplicate keys.")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise CardPackError("Card metadata contains an invalid number.")


def _text(record: dict, key: str, limit: int, *, multiline: bool = False) -> str:
    value = record.get(key, "")
    if not isinstance(value, str) or len(value) > limit or any(
        ord(char) < 32 and (not multiline or char not in "\n\r\t") for char in value
    ):
        raise CardPackError(f"A card has an invalid {key} field.")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise CardPackError("Card metadata contains invalid text.") from error
    return value if multiline else value.strip()


def _read_member(archive: ZipFile, name: str, limit: int) -> bytes:
    with archive.open(name) as source:
        data = source.read(limit + 1)
    if len(data) > limit or len(data) != archive.getinfo(name).file_size:
        raise CardPackError("An archive member exceeds its supported size.")
    return data


def _image(data: bytes, remaining_pixels: int) -> tuple[PackImage, int]:
    buffer = QBuffer()
    buffer.setData(data)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    image_format = bytes(reader.format()).decode("ascii", errors="ignore").lower()
    size = reader.size()
    suffix = {"png": ".png", "jpeg": ".jpg", "bmp": ".bmp", "webp": ".webp"}.get(
        image_format,
    )
    pixels = size.width() * size.height()
    if (suffix is None or size.width() <= 0 or size.height() <= 0
            or pixels > min(MAX_IMAGE_PIXELS, remaining_pixels)):
        raise CardPackError("An image is unsupported or exceeds the pixel limit.")
    decoded = reader.read()
    if decoded.isNull():
        raise CardPackError("An image is damaged or unreadable.")
    # Decode once on the worker; the GUI receives only a small preview to render.
    if decoded.width() > 1024 or decoded.height() > 180:
        decoded = decoded.scaled(1024, 180, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
    preview = QBuffer()
    preview.open(QIODevice.OpenModeFlag.WriteOnly)
    if not decoded.save(preview, "PNG"):
        raise CardPackError("An image preview could not be prepared.")
    return PackImage(data, suffix, hashlib.sha256(data).hexdigest(), bytes(preview.data())), pixels


def _validate_members(archive: ZipFile) -> set[str]:
    names: set[str] = set()
    folded: set[str] = set()
    total = 0
    for info in archive.infolist():
        name = info.orig_filename
        path = PurePosixPath(name)
        mode = stat.S_IFMT(info.external_attr >> 16)
        if (not name or "\x00" in name or "\\" in name or ":" in name
                or path.is_absolute() or ".." in path.parts or path.as_posix() != name
                or name.casefold() in folded or mode not in (0, stat.S_IFREG)
                or info.flag_bits & 1 or info.compress_type not in (ZIP_STORED, ZIP_DEFLATED)):
            raise CardPackError("The ZIP contains an unsafe or ambiguous member.")
        image = len(path.parts) == 2 and path.parts[0] == "images"
        if name not in ("cards.json", "README.md") and not image:
            raise CardPackError("The ZIP contains unsupported files.")
        limit = MAX_IMAGE_BYTES if image else MAX_JSON_BYTES
        total += info.file_size
        if info.file_size > limit or total > MAX_TOTAL_BYTES:
            raise CardPackError("The ZIP exceeds the uncompressed size limit.")
        folded.add(name.casefold())
        names.add(name)
    if "cards.json" not in names:
        raise CardPackError("The ZIP does not contain card metadata.")
    return names


def _card(record: object, images: dict[str, PackImage]) -> PackCard:
    if not isinstance(record, dict):
        raise CardPackError("Card metadata must contain objects.")
    kind = CardKind(record.get("kind"))
    title = _text(record, "title", 512)
    if not title:
        raise CardPackError("Each card needs a title.")
    tags = record.get("tags", [])
    if not isinstance(tags, list) or len(tags) > MAX_TAGS_PER_CARD or any(
        not isinstance(tag, str) or not tag or len(tag) > MAX_TAG_LENGTH
        or any(ord(char) < 32 for char in tag) for tag in tags
    ):
        raise CardPackError("A card has invalid tags.")
    for tag in tags:
        tag.encode("utf-8")
    favorite = record.get("favorite", False)
    if type(favorite) is not bool:
        raise CardPackError("A card has an invalid favorite flag.")
    created = _text(record, "created_at", 64)
    if created:
        date = datetime.fromisoformat(created)
        if date.tzinfo is None:
            raise CardPackError("A card creation date needs a timezone.")
        created = date.astimezone(UTC).isoformat(timespec="seconds")
    image_name = _text(record, "image", 512)
    image = images.get(image_name)
    if (kind is CardKind.NOTE and image_name) or (image_name and image is None):
        raise CardPackError("A card references an invalid image.")
    available = kind is CardKind.NOTE or image is not None
    declared = record.get("image_available", available)
    if type(declared) is not bool or declared != available:
        raise CardPackError("A card has inconsistent image availability.")
    return PackCard(kind, _text(record, "game", MAX_GAME_LENGTH), title,
                    _text(record, "content", 200_000, multiline=True), normalize_tags(tags),
                    favorite, created, image)


def load_card_pack(source: Path, *, cancelled: CancelCheck | None = None) -> CardPack:
    """Snapshot a bounded ZIP, validate all entries, and retain immutable image bytes."""
    try:
        check_cancelled(cancelled)
        with source.open("rb") as stream:
            data = stream.read(MAX_PACK_BYTES + 1)
        if len(data) > MAX_PACK_BYTES:
            raise CardPackError("The card pack exceeds 128 MiB.")
        _preflight_directory(data)
        with ZipFile(io.BytesIO(data)) as archive:
            names = _validate_members(archive)
            manifest = json.loads(_read_member(archive, "cards.json", MAX_JSON_BYTES).decode("utf-8"),
                                  object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            if (not isinstance(manifest, dict) or manifest.get("format") != EXPORT_FORMAT
                    or type(manifest.get("version")) is not int
                    or manifest["version"] != EXPORT_VERSION):
                raise CardPackError("This is not a supported Gaming Buddy card pack.")
            records = manifest.get("cards")
            if not isinstance(records, list) or not 1 <= len(records) <= MAX_CARDS:
                raise CardPackError("The card pack must contain between 1 and 1000 cards.")
            referenced = {record.get("image") for record in records
                          if isinstance(record, dict) and isinstance(record.get("image"), str)
                          and record["image"]}
            if referenced != names - {"cards.json", "README.md"}:
                raise CardPackError("The card pack contains missing or unreferenced images.")
            images, pixels = {}, 0
            for name in sorted(referenced):
                check_cancelled(cancelled)
                image, count = _image(
                    _read_member(archive, name, MAX_IMAGE_BYTES), MAX_TOTAL_PIXELS - pixels,
                )
                pixels += count
                if pixels > MAX_TOTAL_PIXELS:
                    raise CardPackError("Images exceed the card pack's total pixel limit.")
                images[name] = image
            check_cancelled(cancelled)
            return CardPack(tuple(_card(record, images) for record in records))
    except CardPackError:
        raise
    except (OSError, ValueError, TypeError, BadZipFile, RuntimeError, EOFError,
            NotImplementedError, RecursionError, OverflowError) as error:
        raise CardPackError("The card pack is damaged, unreadable, or has invalid metadata.") from error
