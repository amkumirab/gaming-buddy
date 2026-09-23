from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from gaming_buddy.models import Card, CardKind

EXPORT_FORMAT = "gaming-buddy-cards"
EXPORT_VERSION = 1
MAX_IMAGE_BYTES = 256 * 1024 * 1024
_UNSAFE_FILENAME = re.compile(r"[^\w.-]+", re.UNICODE)


class CardExportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CardExportSummary:
    card_count: int
    image_count: int
    missing_image_count: int


def create_card_export(destination: Path, cards: list[Card]) -> CardExportSummary:
    if not cards:
        raise CardExportError("Select at least one card to export.")

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    image_sources: dict[str, Path] = {}
    archived_sources: dict[Path, str] = {}
    used_names: set[str] = set()
    missing_images = 0

    for index, card in enumerate(cards, start=1):
        image_archive = ""
        if card.kind is CardKind.IMAGE:
            source = Path(card.image_path)
            if source.is_file():
                try:
                    source = source.resolve()
                    size = source.stat().st_size
                except OSError as exc:
                    raise CardExportError(f"Could not read image: {source.name}") from exc
                if size > MAX_IMAGE_BYTES:
                    raise CardExportError(f"The image is too large to export safely: {source.name}")
                image_archive = archived_sources.get(source, "")
                if not image_archive:
                    filename = _unique_image_name(card, source, index, used_names)
                    image_archive = f"images/{filename}"
                    archived_sources[source] = image_archive
                    image_sources[image_archive] = source
            else:
                missing_images += 1
        records.append(_card_record(card, image_archive))

    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    manifest = {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "created_at": created_at,
        "cards": records,
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    readme_bytes = _build_readme(records, created_at).encode("utf-8")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("README.md", readme_bytes)
            archive.writestr("cards.json", manifest_bytes)
            for archive_name, source in image_sources.items():
                archive.write(source, archive_name)
        os.replace(temporary_path, destination)
    except (OSError, ValueError) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise CardExportError(f"Could not create the card export: {exc}") from exc

    return CardExportSummary(
        card_count=len(records),
        image_count=len(image_sources),
        missing_image_count=missing_images,
    )


def _unique_image_name(
    card: Card,
    source: Path,
    index: int,
    used_names: set[str],
) -> str:
    suffix = source.suffix.casefold()
    if not suffix or len(suffix) > 10 or not suffix[1:].isalnum():
        suffix = ".png"
    base = _safe_filename(card.title) or _safe_filename(source.stem) or "image"
    candidate = f"{index:03d}-{base}{suffix}"
    number = 2
    while candidate.casefold() in used_names:
        candidate = f"{index:03d}-{base}-{number}{suffix}"
        number += 1
    used_names.add(candidate.casefold())
    return candidate


def _safe_filename(value: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("-", value.strip()).strip(" .-_")
    return cleaned[:80].rstrip(" .-_")


def _card_record(card: Card, image_archive: str) -> dict[str, Any]:
    return {
        "kind": card.kind.value,
        "title": card.title,
        "game": card.game,
        "content": card.content,
        "tags": list(card.tags),
        "favorite": card.favorite,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
        "image": image_archive,
        "image_available": card.kind is not CardKind.IMAGE or bool(image_archive),
    }


def _build_readme(records: list[dict[str, Any]], created_at: str) -> str:
    lines = [
        "# Gaming Buddy card export",
        "",
        f"Exported {len(records)} card(s) on {created_at}.",
        "",
        "The original card metadata is available in `cards.json`.",
        "",
    ]
    for index, record in enumerate(records, start=1):
        title = _markdown_text(str(record["title"])) or "Untitled card"
        lines.extend((f"## {index}. {title}", ""))
        details = [
            f"- **Game:** {_markdown_text(str(record['game'])) or 'General'}",
            f"- **Type:** {str(record['kind']).title()}",
        ]
        tags = record["tags"]
        if tags:
            details.append(
                "- **Tags:** " + ", ".join(f"`{_inline_code(str(tag))}`" for tag in tags)
            )
        if record["favorite"]:
            details.append("- **Favorite:** Yes")
        lines.extend((*details, ""))

        image = str(record["image"])
        if image:
            lines.extend((f"![{title}]({quote(image, safe='/')})", ""))
        elif record["kind"] == CardKind.IMAGE.value:
            lines.extend(("_The original image was unavailable when this export was created._", ""))

        content = str(record["content"]).strip()
        if content:
            heading = "Extracted text" if record["kind"] == CardKind.IMAGE.value else "Note"
            lines.extend((f"### {heading}", "", _markdown_block(content), ""))
        lines.extend(("---", ""))
    return "\n".join(lines)


def _markdown_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("#", "\\#").replace("*", "\\*").replace("_", "\\_")


def _inline_code(value: str) -> str:
    return value.replace("`", "'").replace("\n", " ").replace("\r", " ")


def _markdown_block(value: str) -> str:
    return "\n".join(f"    {line}" if line else "    " for line in value.splitlines())
