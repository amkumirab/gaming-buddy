from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from gaming_buddy.card_preview import (
    CardPreviewPanel,
    format_file_size,
    format_saved_at,
    image_summary,
)
from gaming_buddy.models import Card, CardKind


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _save_image(path: Path, width: int = 320, height: int = 180) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#7657ff"))
    assert image.save(str(path), "PNG", 100)


def test_formatters_handle_sizes_dates_and_missing_values(tmp_path: Path) -> None:
    assert format_file_size(512) == "512 B"
    assert format_file_size(1536) == "1.5 KB"
    assert "03 Sep 2026" in format_saved_at("2026-09-03T14:20:00")
    assert format_saved_at("invalid") == "Saved date unavailable"
    assert image_summary(tmp_path / "missing.png") == "Image file missing"


def test_image_card_shows_smooth_preview_and_details(
    application: QApplication,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "map.png"
    _save_image(image_path)
    card = Card(
        1,
        CardKind.IMAGE,
        "Control",
        "Maintenance map",
        content="SAFE CODE 0451",
        image_path=str(image_path),
        favorite=True,
        pinned=True,
        created_at="2026-09-03T14:20:00+00:00",
        tags=("map", "code"),
    )
    panel = CardPreviewPanel()

    panel.set_card(card)

    assert panel.card is card
    assert panel.title.text() == "Maintenance map"
    assert panel.kind.text() == "IMAGE"
    assert panel.game.text().startswith("Control · Favorite · Pinned")
    assert "#map" in panel.game.text()
    assert "#code" in panel.game.text()
    assert "320 × 180 px" in panel.metadata.text()
    assert panel.content.toPlainText() == "SAFE CODE 0451"
    assert panel.pin_button.text() == "Show pin"
    assert panel.copy_button.text() == "Copy image"
    assert panel.image.pixmap() is not None
    assert not panel.image.pixmap().isNull()
    assert panel.extract_button.isEnabled()
    panel.close()


def test_note_card_uses_full_text_preview(application: QApplication) -> None:
    card = Card(
        2,
        CardKind.NOTE,
        "Elden Ring",
        "Build order",
        content="Upgrade vigor before strength.\nKeep a medium equipment load.",
        created_at="2026-09-03T09:15:00+00:00",
    )
    panel = CardPreviewPanel()

    panel.set_card(card)

    assert panel.kind.text() == "NOTE"
    assert panel.content.toPlainText() == card.content
    assert panel.copy_button.text() == "Copy note"
    assert panel.extract_button.isHidden()
    assert panel.image.isHidden()
    panel.close()


def test_preview_actions_emit_the_selected_card(
    application: QApplication,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "clue.png"
    _save_image(image_path)
    card = Card(3, CardKind.IMAGE, "Game", "Clue", image_path=str(image_path))
    panel = CardPreviewPanel()
    requested: list[tuple[str, Card]] = []
    panel.pin_requested.connect(lambda value: requested.append(("pin", value)))
    panel.edit_requested.connect(lambda value: requested.append(("edit", value)))
    panel.copy_requested.connect(lambda value: requested.append(("copy", value)))
    panel.extract_text_requested.connect(
        lambda value: requested.append(("extract", value))
    )
    panel.set_card(card)

    panel.pin_button.click()
    panel.edit_button.click()
    panel.copy_button.click()
    panel.extract_button.click()

    assert requested == [
        ("pin", card),
        ("edit", card),
        ("copy", card),
        ("extract", card),
    ]
    panel.close()


def test_clear_disables_preview_actions(application: QApplication) -> None:
    panel = CardPreviewPanel()
    panel.set_card(Card(4, CardKind.NOTE, "Game", "Note", content="Text"))

    panel.clear()

    assert panel.card is None
    assert not panel.pin_button.isEnabled()
    assert not panel.edit_button.isEnabled()
    assert not panel.copy_button.isEnabled()
    assert panel.content.isHidden()
    panel.close()
