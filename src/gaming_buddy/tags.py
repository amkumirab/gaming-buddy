from __future__ import annotations

from collections.abc import Iterable

MAX_TAGS_PER_CARD = 12
MAX_TAG_LENGTH = 28


def normalize_tags(values: str | Iterable[str]) -> tuple[str, ...]:
    candidates = values.replace(";", ",").split(",") if isinstance(values, str) else values
    tags: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        tag = " ".join(str(candidate).strip().lstrip("#").split())[:MAX_TAG_LENGTH]
        normalized = tag.casefold()
        if not tag or normalized in seen:
            continue
        seen.add(normalized)
        tags.append(tag)
        if len(tags) == MAX_TAGS_PER_CARD:
            break
    return tuple(tags)


def format_tags(tags: Iterable[str]) -> str:
    return "  ".join(f"#{tag}" for tag in tags)
