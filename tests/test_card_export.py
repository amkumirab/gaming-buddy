from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

import gaming_buddy.card_export as export_module
from gaming_buddy.card_export import CardExportError, create_card_export
from gaming_buddy.models import Card, CardKind


def test_export_contains_readable_index_metadata_and_original_images(tmp_path: Path) -> None:
    image = tmp_path / "source" / "map original.PNG"
    image.parent.mkdir()
    image.write_bytes(b"original-image-bytes")
    cards = [
        Card(
            id=1,
            kind=CardKind.NOTE,
            game="Control",
            title="Clock puzzle",
            content="Turn left\nThen right",
            tags=("puzzle", "route"),
            favorite=True,
            created_at="2026-09-20T12:00:00+00:00",
            updated_at="2026-09-21T12:00:00+00:00",
        ),
        Card(
            id=2,
            kind=CardKind.IMAGE,
            game="Alan Wake 2",
            title="Map: Hotel / Lobby?",
            content="Room 665",
            image_path=str(image),
            tags=("map",),
        ),
    ]

    destination = tmp_path / "cards.zip"
    summary = create_card_export(destination, cards)

    assert summary.card_count == 2
    assert summary.image_count == 1
    assert summary.missing_image_count == 0
    with ZipFile(destination) as archive:
        names = archive.namelist()
        assert names == [
            "README.md",
            "cards.json",
            "images/002-Map-Hotel-Lobby.png",
        ]
        assert archive.read(names[-1]) == b"original-image-bytes"
        readme = archive.read("README.md").decode("utf-8")
        assert "## 1. Clock puzzle" in readme
        assert "    Turn left\n    Then right" in readme
        assert "![Map: Hotel / Lobby?](images/002-Map-Hotel-Lobby.png)" in readme
        manifest = json.loads(archive.read("cards.json"))

    assert manifest["format"] == "gaming-buddy-cards"
    assert manifest["version"] == 1
    assert manifest["cards"][0]["favorite"] is True
    assert manifest["cards"][0]["tags"] == ["puzzle", "route"]
    assert manifest["cards"][1]["image"] == "images/002-Map-Hotel-Lobby.png"
    assert "image_path" not in manifest["cards"][1]
    assert "id" not in manifest["cards"][1]


def test_export_reuses_one_file_for_cards_with_the_same_image(tmp_path: Path) -> None:
    image = tmp_path / "clue.webp"
    image.write_bytes(b"shared")
    cards = [
        Card(1, CardKind.IMAGE, "Game", "First", image_path=str(image)),
        Card(2, CardKind.IMAGE, "Game", "Second", image_path=str(image)),
    ]

    summary = create_card_export(tmp_path / "shared.zip", cards)

    assert summary.image_count == 1
    with ZipFile(tmp_path / "shared.zip") as archive:
        manifest = json.loads(archive.read("cards.json"))
        assert manifest["cards"][0]["image"] == manifest["cards"][1]["image"]
        assert len([name for name in archive.namelist() if name.startswith("images/")]) == 1


def test_export_keeps_missing_image_card_and_reports_it(tmp_path: Path) -> None:
    card = Card(
        1,
        CardKind.IMAGE,
        "Game",
        "Unavailable clue",
        image_path=str(tmp_path / "missing.png"),
    )

    summary = create_card_export(tmp_path / "missing.zip", [card])

    assert summary == export_module.CardExportSummary(1, 0, 1)
    with ZipFile(tmp_path / "missing.zip") as archive:
        manifest = json.loads(archive.read("cards.json"))
        readme = archive.read("README.md").decode("utf-8")
    assert manifest["cards"][0]["image_available"] is False
    assert "original image was unavailable" in readme


def test_export_requires_cards(tmp_path: Path) -> None:
    with pytest.raises(CardExportError, match="at least one card"):
        create_card_export(tmp_path / "empty.zip", [])


def test_failed_export_does_not_replace_existing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "large.png"
    image.write_bytes(b"too-large")
    destination = tmp_path / "existing.zip"
    destination.write_bytes(b"keep-this")
    monkeypatch.setattr(export_module, "MAX_IMAGE_BYTES", 2)
    card = Card(1, CardKind.IMAGE, "Game", "Large", image_path=str(image))

    with pytest.raises(CardExportError, match="too large"):
        create_card_export(destination, [card])

    assert destination.read_bytes() == b"keep-this"
    assert not list(tmp_path.glob(".existing.zip.*.tmp"))
