import hashlib
import json
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
from gaming_buddy.workspace_presets import PresetPinLayout


def test_workspace_backup_round_trip_and_duplicate_detection(tmp_path):
    source_settings = QSettings(
        str(tmp_path / "source-settings.ini"),
        QSettings.Format.IniFormat,
    )
    source_settings.setValue("game", "Control")
    source_settings.setValue("click_through", True)
    source_settings.setValue("profiles/auto_hide_pins", True)
    source_settings.setValue("preview/visible", False)
    source_settings.setValue("recognition/language", "en-US")
    source_settings.setValue("focus/opacity", 65)
    source_settings.setValue("updates/automatic_checks", False)
    source_settings.setValue("shortcuts/capture_area", "Ctrl+Alt+C")
    source_settings.setValue("shortcuts/quick_finder", "Ctrl+Alt+F")
    source_settings.setValue("shortcuts/toggle_focus_mode", "Ctrl+Alt+M")
    source_settings.setValue("shortcuts/previous_pin", "Ctrl+Alt+Left")
    source_settings.setValue("shortcuts/next_pin", "Ctrl+Alt+Right")
    source_settings.setValue("shortcuts/restore_pins", "Ctrl+Alt+Up")
    source_settings.setValue("window_geometry", "not portable")

    image_path = tmp_path / "source-captures" / "map.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"lossless-image-content")
    source_store = CardStore(tmp_path / "source.sqlite3")
    try:
        note = source_store.add(
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
                tags=("puzzle", "clue"),
            )
        )
        image = source_store.add(
            Card(
                id=None,
                kind=CardKind.IMAGE,
                game="Control",
                title="Map",
                content="SAFE CODE 0451",
                image_path=str(image_path),
                tags=("map", "code"),
                pinned=True,
            )
        )
        assert note.id is not None and image.id is not None
        source_store.save_workspace_preset(
            "Control",
            "Puzzle desk",
            (
                PresetPinLayout(note.id, True, 25, 30, 440, 260, 0.7, True, True),
                PresetPinLayout(image.id, False, 520, 30, 500, 300, 0.8, False, False),
            ),
        )
        backup = tmp_path / "workspace.zip"
        created = create_workspace_backup(backup, source_store, source_settings)
    finally:
        source_store.close()

    assert created.card_count == 2
    assert created.image_count == 1
    assert created.missing_image_count == 0
    assert created.preset_count == 1
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
        assert restored_note.tags == ("clue", "puzzle")
        assert restored_image.tags == ("code", "map")
        assert restored_image.image_path.startswith(str(restored_captures))
        assert restored_image.image_path != str(image_path)
        assert restored_image.content == "SAFE CODE 0451"
        assert Path(restored_image.image_path).read_bytes() == b"lossless-image-content"
        assert restored_settings.value("game") == "Control"
        assert restored_settings.value("click_through", type=bool) is True
        assert restored_settings.value("profiles/auto_hide_pins", type=bool) is True
        assert restored_settings.value("preview/visible", type=bool) is False
        assert restored_settings.value("recognition/language") == "en-US"
        assert restored_settings.value("focus/opacity", type=int) == 65
        assert restored_settings.value("updates/automatic_checks", type=bool) is False
        assert restored_settings.value("shortcuts/quick_finder") == "Ctrl+Alt+F"
        assert restored_settings.value("shortcuts/toggle_focus_mode") == "Ctrl+Alt+M"
        assert restored_settings.value("shortcuts/previous_pin") == "Ctrl+Alt+Left"
        assert restored_settings.value("shortcuts/next_pin") == "Ctrl+Alt+Right"
        assert restored_settings.value("shortcuts/restore_pins") == "Ctrl+Alt+Up"
        assert restored_settings.value("window_geometry") is None
        preset = restored_store.active_workspace_preset("Control")
        assert preset is not None
        assert preset.name == "Puzzle desk"
        layouts_by_title = {
            restored_store.get(layout.card_id).title: layout for layout in preset.pins
        }
        assert layouts_by_title["Puzzle clue"].x == 25
        assert layouts_by_title["Puzzle clue"].visible is True
        assert layouts_by_title["Map"].x == 520
        assert layouts_by_title["Map"].visible is False

        assert restored_store.update_tags(restored_image.id, ("local",))
        repeated = restore_workspace_backup(
            backup,
            restored_store,
            restored_captures,
            restored_settings,
        )
        assert repeated.imported_cards == 0
        assert repeated.duplicate_cards == 2
        assert repeated.restored_presets == 1
        assert len(restored_store.list()) == 2
        assert len(restored_store.list_workspace_presets("Control")) == 1
        assert restored_store.get(restored_image.id).tags == ("code", "local", "map")
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


def test_version_one_backups_remain_supported(tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    with CardStore(tmp_path / "source.sqlite3") as store:
        store.add(Card(None, CardKind.NOTE, "Game", "Legacy clue", content="Text"))
        current = tmp_path / "current.zip"
        create_workspace_backup(current, store, settings)

    legacy = tmp_path / "legacy.zip"
    with ZipFile(current, "r") as source:
        cards = source.read("cards.json")
        portable_settings = source.read("settings.json")
        manifest = json.loads(source.read("manifest.json"))
    manifest["version"] = 1
    manifest.pop("preset_count", None)
    manifest["checksums"] = {
        "cards.json": hashlib.sha256(cards).hexdigest(),
        "settings.json": hashlib.sha256(portable_settings).hexdigest(),
    }
    with ZipFile(legacy, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("cards.json", cards)
        archive.writestr("settings.json", portable_settings)

    summary = inspect_workspace_backup(legacy)
    assert summary.card_count == 1
    assert summary.preset_count == 0
    with CardStore(tmp_path / "destination.sqlite3") as store:
        result = restore_workspace_backup(legacy, store, tmp_path / "captures", settings)
        assert result.imported_cards == 1
        assert result.restored_presets == 0
