from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class CardKind(StrEnum):
    NOTE = "note"
    IMAGE = "image"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class Card:
    id: int | None
    kind: CardKind
    game: str
    title: str
    content: str = ""
    image_path: str = ""
    opacity: float = 0.88
    x: int = 80
    y: int = 80
    width: int = 320
    height: int = 220
    favorite: bool = False
    pinned: bool = False
    locked: bool = False
    collapsed: bool = False
    created_at: str = ""
    updated_at: str = ""
    deleted_at: str = ""
    tags: tuple[str, ...] = ()

    def with_timestamps(self) -> Card:
        now = utc_now()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
        return self
