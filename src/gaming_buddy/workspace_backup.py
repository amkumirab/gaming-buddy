from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from PySide6.QtCore import QSettings

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore

BACKUP_FORMAT = "gaming-buddy-workspace"
BACKUP_VERSION = 1
MAX_ARCHIVE_FILES = 10_000
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_JSON_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 256 * 1024 * 1024
PORTABLE_SETTING_KEYS = {
    "game",
    "click_through",
    "profiles/auto_hide_pins",
    "profiles/auto_switch",
    "profiles/executable_map",
    "preview/visible",
    "recognition/language",
    "shortcuts/toggle_panel",
    "shortcuts/quick_finder",
    "shortcuts/capture_area",
    "shortcuts/toggle_click_through",
}


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BackupSummary:
    created_at: str
    card_count: int
    image_count: int
    missing_image_count: int
    settings_count: int


@dataclass(frozen=True, slots=True)
class RestoreResult:
    imported_cards: int
    duplicate_cards: int
    skipped_cards: int
    restored_settings: int


def create_workspace_backup(
    destination: Path,
    store: CardStore,
    settings: QSettings,
) -> BackupSummary:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    cards = store.list()
    records: list[dict[str, Any]] = []
    image_sources: dict[str, Path] = {}
    missing_images = 0

    for index, card in enumerate(cards, start=1):
        image_archive = ""
        if card.kind is CardKind.IMAGE:
            source = Path(card.image_path)
            if source.is_file():
                if source.stat().st_size > MAX_IMAGE_BYTES:
                    raise BackupError(f"The capture is too large to back up safely: {source.name}")
                safe_name = source.name or f"capture-{index}.png"
                image_archive = f"captures/{index:06d}-{safe_name}"
                image_sources[image_archive] = source
            else:
                missing_images += 1
        records.append(_card_to_record(card, image_archive))

    portable_settings = _portable_settings(settings)
    cards_bytes = _json_bytes(records)
    settings_bytes = _json_bytes(portable_settings)
    checksums = {
        "cards.json": _sha256_bytes(cards_bytes),
        "settings.json": _sha256_bytes(settings_bytes),
    }
    for archive_name, source in image_sources.items():
        checksums[archive_name] = _sha256_file(source)

    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    summary = BackupSummary(
        created_at=created_at,
        card_count=len(records),
        image_count=len(image_sources),
        missing_image_count=missing_images,
        settings_count=len(portable_settings),
    )
    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": created_at,
        "card_count": summary.card_count,
        "image_count": summary.image_count,
        "missing_image_count": summary.missing_image_count,
        "settings_count": summary.settings_count,
        "checksums": checksums,
    }

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", _json_bytes(manifest))
            archive.writestr("cards.json", cards_bytes)
            archive.writestr("settings.json", settings_bytes)
            for archive_name, source in image_sources.items():
                archive.write(source, archive_name)
        os.replace(temporary, destination)
    except (OSError, BadZipFile) as exc:
        temporary.unlink(missing_ok=True)
        raise BackupError(f"Could not create the backup: {exc}") from exc
    return summary


def inspect_workspace_backup(source: Path) -> BackupSummary:
    manifest, _, _ = _read_and_verify(source)
    return BackupSummary(
        created_at=str(manifest["created_at"]),
        card_count=int(manifest["card_count"]),
        image_count=int(manifest["image_count"]),
        missing_image_count=int(manifest.get("missing_image_count", 0)),
        settings_count=int(manifest["settings_count"]),
    )


def restore_workspace_backup(
    source: Path,
    store: CardStore,
    captures_dir: Path,
    settings: QSettings,
) -> RestoreResult:
    _, records, portable_settings = _read_and_verify(source)
    captures_dir.mkdir(parents=True, exist_ok=True)
    existing_identities = {_card_identity(card) for card in store.list()}
    imported = 0
    duplicates = 0
    skipped = 0

    with ZipFile(source, "r") as archive:
        for record in records:
            try:
                card, image_archive = _record_to_card(record)
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue

            image_bytes: bytes | None = None
            image_digest = ""
            if card.kind is CardKind.IMAGE:
                if not image_archive:
                    skipped += 1
                    continue
                try:
                    image_bytes = archive.read(image_archive)
                except KeyError:
                    skipped += 1
                    continue
                image_digest = _sha256_bytes(image_bytes)

            identity = _record_identity(record, image_digest)
            if identity in existing_identities:
                duplicates += 1
                continue

            if image_bytes is not None:
                original_name = PurePosixPath(image_archive).name
                destination = captures_dir / f"restored-{uuid.uuid4().hex[:10]}-{original_name}"
                try:
                    destination.write_bytes(image_bytes)
                except OSError:
                    skipped += 1
                    continue
                card.image_path = str(destination)

            store.add(card)
            existing_identities.add(identity)
            imported += 1

    restored_settings = 0
    for key, value in portable_settings.items():
        if _is_portable_setting(key):
            settings.setValue(key, value)
            restored_settings += 1
    settings.sync()
    return RestoreResult(imported, duplicates, skipped, restored_settings)


def _read_and_verify(
    source: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    try:
        with ZipFile(source, "r") as archive:
            infos = archive.infolist()
            _validate_archive_members(infos)
            manifest = _read_json(archive, "manifest.json")
            if not isinstance(manifest, dict):
                raise BackupError("The backup manifest is invalid.")
            if manifest.get("format") != BACKUP_FORMAT:
                raise BackupError("This is not a Gaming Buddy workspace backup.")
            if manifest.get("version") != BACKUP_VERSION:
                raise BackupError("This backup version is not supported.")
            checksums = manifest.get("checksums")
            if not isinstance(checksums, dict):
                raise BackupError("The backup manifest is incomplete.")
            names = {info.filename for info in infos}
            if names != {"manifest.json", *checksums}:
                raise BackupError("The backup contains files not listed in its manifest.")
            for name, expected in checksums.items():
                if not isinstance(name, str) or not isinstance(expected, str) or name not in names:
                    raise BackupError("The backup manifest references a missing file.")
                actual = _sha256_archive_member(archive, name)
                if actual != expected:
                    raise BackupError(f"Backup integrity check failed for {name}.")
            records = _read_json(archive, "cards.json")
            portable_settings = _read_json(archive, "settings.json")
    except (OSError, BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError(f"Could not read the backup: {exc}") from exc

    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise BackupError("The card list in this backup is invalid.")
    if not isinstance(portable_settings, dict):
        raise BackupError("The settings in this backup are invalid.")
    if any(
        not isinstance(key, str)
        or not _is_portable_setting(key)
        or not isinstance(value, (bool, int, float, str, type(None)))
        for key, value in portable_settings.items()
    ):
        raise BackupError("The backup contains an unsupported setting.")
    try:
        card_count = int(manifest.get("card_count", -1))
        image_count = int(manifest.get("image_count", -1))
        missing_image_count = int(manifest.get("missing_image_count", -1))
        settings_count = int(manifest.get("settings_count", -1))
    except (TypeError, ValueError) as exc:
        raise BackupError("The backup manifest contains invalid counts.") from exc
    if not isinstance(manifest.get("created_at"), str) or not manifest["created_at"]:
        raise BackupError("The backup creation date is missing.")
    if min(card_count, image_count, missing_image_count, settings_count) < 0:
        raise BackupError("The backup manifest contains negative counts.")
    if card_count != len(records):
        raise BackupError("The backup card count does not match its manifest.")
    if settings_count != len(portable_settings):
        raise BackupError("The backup settings count does not match its manifest.")
    archive_images = {name for name in checksums if name.startswith("captures/")}
    if image_count != len(archive_images):
        raise BackupError("The backup image count does not match its manifest.")
    for record in records:
        image_archive = str(record.get("image_archive", ""))
        if image_archive and (
            not image_archive.startswith("captures/") or image_archive not in archive_images
        ):
            raise BackupError("A card references an invalid backup image.")
    missing_records = sum(
        1
        for record in records
        if record.get("kind") == CardKind.IMAGE.value and not record.get("image_archive")
    )
    if missing_image_count != missing_records:
        raise BackupError("The missing-image count does not match the backup contents.")
    return manifest, records, portable_settings


def _validate_archive_members(infos: list[ZipInfo]) -> None:
    if len(infos) > MAX_ARCHIVE_FILES:
        raise BackupError("The backup contains too many files.")
    total_size = 0
    seen: set[str] = set()
    for info in infos:
        path = PurePosixPath(info.filename)
        if (
            not info.filename
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in info.filename
            or info.filename in seen
        ):
            raise BackupError("The backup contains an unsafe file path.")
        seen.add(info.filename)
        if info.filename.startswith("captures/") and info.file_size > MAX_IMAGE_BYTES:
            raise BackupError("A backup image is too large to restore safely.")
        total_size += info.file_size
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise BackupError("The backup is too large to restore safely.")


def _read_json(archive: ZipFile, name: str) -> Any:
    info = archive.getinfo(name)
    if info.file_size > MAX_JSON_BYTES:
        raise BackupError(f"{name} is too large.")
    return json.loads(archive.read(name).decode("utf-8"))


def _portable_settings(settings: QSettings) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in settings.allKeys():
        if not _is_portable_setting(key):
            continue
        value = settings.value(key)
        if isinstance(value, (bool, int, float, str)) or value is None:
            values[key] = value
        else:
            values[key] = str(value)
    return values


def _is_portable_setting(key: str) -> bool:
    return key in PORTABLE_SETTING_KEYS


def _card_to_record(card: Card, image_archive: str) -> dict[str, Any]:
    return {
        "kind": card.kind.value,
        "game": card.game,
        "title": card.title,
        "content": card.content,
        "image_archive": image_archive,
        "opacity": card.opacity,
        "x": card.x,
        "y": card.y,
        "width": card.width,
        "height": card.height,
        "favorite": card.favorite,
        "pinned": card.pinned,
        "locked": card.locked,
        "collapsed": card.collapsed,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


def _record_to_card(record: dict[str, Any]) -> tuple[Card, str]:
    kind = CardKind(str(record["kind"]))
    title = str(record["title"]).strip()
    if not title:
        raise ValueError("Card title is empty")
    card = Card(
        id=None,
        kind=kind,
        game=str(record.get("game", "General")).strip() or "General",
        title=title,
        content=str(record.get("content", "")),
        opacity=float(record.get("opacity", 0.88)),
        x=int(record.get("x", 80)),
        y=int(record.get("y", 80)),
        width=int(record.get("width", 320)),
        height=int(record.get("height", 220)),
        favorite=bool(record.get("favorite", False)),
        pinned=bool(record.get("pinned", False)),
        locked=bool(record.get("locked", False)),
        collapsed=bool(record.get("collapsed", False)),
        created_at=str(record.get("created_at", "")),
        updated_at=str(record.get("updated_at", "")),
    )
    return card, str(record.get("image_archive", ""))


def _card_identity(card: Card) -> tuple[str, ...]:
    image_digest = ""
    if card.kind is CardKind.IMAGE and Path(card.image_path).is_file():
        image_digest = _sha256_file(Path(card.image_path))
    return (
        card.kind.value,
        card.game.strip().casefold(),
        card.title.strip(),
        card.content,
        card.created_at,
        image_digest,
    )


def _record_identity(record: dict[str, Any], image_digest: str) -> tuple[str, ...]:
    return (
        str(record.get("kind", "")),
        str(record.get("game", "")).strip().casefold(),
        str(record.get("title", "")).strip(),
        str(record.get("content", "")),
        str(record.get("created_at", "")),
        image_digest,
    )


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_archive_member(archive: ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with archive.open(name, "r") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
