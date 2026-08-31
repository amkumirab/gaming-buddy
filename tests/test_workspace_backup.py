from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from PySide6.QtCore import QSettings

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore
from gaming_buddy.workspace_backup import (
    BackupError,
    create_workspace_backup,
    inspect_workspace_backup,
    restore_workspace_backup,
)


def test_workspace_backup_round_trip_and_duplicate_detection(tmp_path):
    source_settings = QSettings(
        str(tmp_path / "source-settings.ini"),
        QSettings.Format.IniFormat,
    )
    source_settings.setValue("game", "Control")
    source_settings.setValue("click_through", True)
    source_settings.setValue("profiles/auto_hide_pins", True)
    source_settings.setValue("shortcuts/capture_area", "Ctrl+Alt+C")
    source_settings.setValue("shortcuts/quick_finder", "Ctrl+Alt+F")
    source_settings.setValue("window_geometry", "not portable")

    image_path = tmp_path / "source-captures" / "map.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"lossless-image-content")
    source_store = CardStore(tmp_path / "source.sqlite3")
    try:
        source_store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="Control",
                title="Puzzle clue",
                content="Turn the wheels clockwise.",
                favorite=True,
                pinned=True,
                locked=True,
                collapsed=True,
            )
        )
        source_store.add(
            Card(
                id=None,
                kind=CardKind.IMAGE,
                game="Control",
                title="Map",
                image_path=str(image_path),
            )
        )
        backup = tmp_path / "workspace.zip"
        created = create_workspace_backup(backup, source_store, source_settings)
    finally:
        source_store.close()

    assert created.card_count == 2
    assert created.image_count == 1
    assert created.missing_image_count == 0
    assert inspect_workspace_backup(backup) == created

    restored_settings = QSettings(
        str(tmp_path / "restored-settings.ini"),
        QSettings.Format.IniFormat,
    )
    restored_settings.setValue("game", "Existing Game")
    restored_captures = tmp_path / "restored-captures"
    restored_store = CardStore(tmp_path / "restored.sqlite3")
    try:
        result = restore_workspace_backup(
            backup,
            restored_store,
            restored_captures,
            restored_settings,
        )
        assert result.imported_cards == 2
        assert result.duplicate_cards == 0
        assert result.skipped_cards == 0
        cards = restored_store.list()
        assert {card.title for card in cards} == {"Puzzle clue", "Map"}
        restored_image = next(card for card in cards if card.kind is CardKind.IMAGE)
        restored_note = next(card for card in cards if card.kind is CardKind.NOTE)
        assert restored_note.locked is True
        assert restored_note.collapsed is True
        assert restored_image.image_path.startswith(str(restored_captures))
        assert restored_image.image_path != str(image_path)
        assert Path(restored_image.image_path).read_bytes() == b"lossless-image-content"
        assert restored_settings.value("game") == "Control"
        assert restored_settings.value("click_through", type=bool) is True
        assert restored_settings.value("profiles/auto_hide_pins", type=bool) is True
        assert restored_settings.value("shortcuts/quick_finder") == "Ctrl+Alt+F"
        assert restored_settings.value("window_geometry") is None

        repeated = restore_workspace_backup(
            backup,
            restored_store,
            restored_captures,
            restored_settings,
        )
        assert repeated.imported_cards == 0
        assert repeated.duplicate_cards == 2
        assert len(restored_store.list()) == 2
    finally:
        restored_store.close()


def test_missing_images_are_reported_and_skipped_on_restore(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    source_store = CardStore(tmp_path / "source.sqlite3")
    try:
        source_store.add(
            Card(
                id=None,
                kind=CardKind.IMAGE,
                game="Game",
                title="Missing capture",
                image_path=str(tmp_path / "missing.png"),
            )
        )
        backup = tmp_path / "missing-image.zip"
        summary = create_workspace_backup(backup, source_store, settings)
    finally:
        source_store.close()

    assert summary.missing_image_count == 1
    destination = CardStore(tmp_path / "destination.sqlite3")
    try:
        result = restore_workspace_backup(
            backup,
            destination,
            tmp_path / "captures",
            settings,
        )
        assert result.skipped_cards == 1
        assert destination.list() == []
    finally:
        destination.close()


def test_unsafe_or_modified_archives_are_rejected(tmp_path):
    unsafe = tmp_path / "unsafe.zip"
    with ZipFile(unsafe, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../outside.txt", "unsafe")
    with pytest.raises(BackupError, match="unsafe file path"):
        inspect_workspace_backup(unsafe)

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    store = CardStore(tmp_path / "cards.sqlite3")
    try:
        store.add(Card(None, CardKind.NOTE, "Game", "Clue", content="Text"))
        original = tmp_path / "original.zip"
        create_workspace_backup(original, store, settings)
    finally:
        store.close()
    modified = tmp_path / "modified.zip"
    with ZipFile(original, "r") as source, ZipFile(modified, "w", ZIP_DEFLATED) as destination:
        for info in source.infolist():
            content = b"[]" if info.filename == "cards.json" else source.read(info.filename)
            destination.writestr(info.filename, content)
    with pytest.raises(BackupError):
        inspect_workspace_backup(modified)
