"""Plan imports off the GUI thread; commit through the GUI-owned SQLite store."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from gaming_buddy.card_pack import (
    MAX_GAME_LENGTH,
    MAX_IMAGE_BYTES,
    CancelCheck,
    CardPack,
    CardPackError,
    PackCard,
    check_cancelled,
)
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@dataclass(frozen=True, slots=True)
class CardImportPlan:
    cards: tuple[PackCard, ...]
    duplicates: int
    missing_images: int


@dataclass(frozen=True, slots=True)
class CardImportResult:
    imported: int
    duplicates: int
    missing_images: int


def _metadata(card: Card | PackCard) -> tuple:
    # Content is deliberately exact: indentation, case, and blank lines are meaningful.
    return (card.kind, card.game.strip().casefold(), card.title.strip(), card.content,
            tuple(sorted(tag.casefold() for tag in card.tags)))


def _owned_digest(path: Path, root: Path, cancelled: CancelCheck | None) -> str | None:
    # Native captures live directly in this owned folder. Never open external/UNC paths.
    if path.parent != root or path.is_symlink():
        return None
    try:
        if not path.is_file() or path.stat().st_size > MAX_IMAGE_BYTES:
            return None
        digest, size = hashlib.sha256(), 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                check_cancelled(cancelled)
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    return None
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def plan_card_import(
    pack: CardPack, indices: Sequence[int], existing: Sequence[Card], captures_dir: Path,
    *, game: str | None = None, cancelled: CancelCheck | None = None,
) -> CardImportPlan:
    """Read matching owned images only; do not write files or use a SQLite connection."""
    if (not indices or any(type(index) is not int or not 0 <= index < len(pack.cards)
                           for index in indices) or len(set(indices)) != len(indices)):
        raise CardPackError("Select valid, distinct cards to import.")
    if game is not None and (not isinstance(game, str) or len(game) > MAX_GAME_LENGTH
                             or any(ord(char) < 32 for char in game)):
        raise CardPackError("Enter a valid destination game.")
    if game is not None:
        try:
            game.encode("utf-8")
        except UnicodeError as error:
            raise CardPackError("Enter a valid destination game.") from error
    selected = [replace(pack.cards[index], game=game.strip()) if game is not None
                else pack.cards[index] for index in indices]
    wanted = {_metadata(card) for card in selected if card.available}
    root = captures_dir.resolve()
    seen: set[tuple] = set()
    digests: dict[Path, str | None] = {}
    for card in existing:
        check_cancelled(cancelled)
        key = _metadata(card)
        if key not in wanted:
            continue
        digest = ""
        if card.kind is CardKind.IMAGE:
            path = Path(card.image_path)
            if path not in digests:
                digests[path] = _owned_digest(path, root, cancelled)
            digest = digests[path]
        if digest is not None:
            seen.add((*key, digest))
    cards, duplicates, missing = [], 0, 0
    for card in selected:
        check_cancelled(cancelled)
        if not card.available:
            missing += 1
            continue
        key = (*_metadata(card), card.image.digest if card.image is not None else "")
        if key in seen:
            duplicates += 1
        else:
            cards.append(card)
            seen.add(key)
    return CardImportPlan(tuple(cards), duplicates, missing)


def _cleanup_owned_copies(created: list[tuple[Path, int | None, int | None]]) -> bool:
    success = True
    for path, device, inode in created:
        try:
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (device, inode) or not stat.S_ISREG(current.st_mode):
                success = False
                continue
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            success = False
    return success


def commit_card_import(
    plan: CardImportPlan, store: CardStore, captures_dir: Path,
) -> CardImportResult:
    """Write new copies, then one transaction; never clean up after a successful commit."""
    created: list[tuple[Path, int | None, int | None]] = []
    saved: dict[str, Path] = {}
    cards: list[Card] = []
    committed = False
    try:
        root = captures_dir.resolve()
        for entry in plan.cards:
            path = ""
            image = entry.image
            if image is not None:
                if image.digest not in saved:
                    root.mkdir(parents=True, exist_ok=True)
                    destination = root / f"pack-{uuid.uuid4().hex}{image.suffix}"
                    with destination.open("xb") as output:
                        created.append((destination, None, None))
                        try:
                            identity = os.fstat(output.fileno())
                        except OSError:
                            identity = destination.lstat()
                            created[-1] = (destination, identity.st_dev, identity.st_ino)
                            raise
                        created[-1] = (destination, identity.st_dev, identity.st_ino)
                        output.write(image.data)
                    saved[image.digest] = destination
                path = str(saved[image.digest])
            cards.append(Card(None, entry.kind, entry.game, entry.title,
                              content=entry.content, image_path=path, tags=entry.tags,
                              favorite=entry.favorite, created_at=entry.created_at))
        store.add_many(cards)
        committed = True
    except (OSError, sqlite3.Error) as error:
        raise CardPackError("The import could not be saved. Existing cards were not changed.") from error
    finally:
        if not committed and not _cleanup_owned_copies(created):
            raise CardPackError("Import failed. Some new image copies could not be removed.")
    return CardImportResult(len(cards), plan.duplicates, plan.missing_images)
