from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore
from gaming_buddy.trash_dialog import TrashDialog, remove_card_image_if_unused


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_recently_deleted_dialog_restores_selected_card(
    application: QApplication, tmp_path
) -> None:
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(Card(None, CardKind.NOTE, "Control", "Puzzle clue"))
        assert store.move_to_trash(card.id)
        dialog = TrashDialog(store, tmp_path)

        assert dialog.card_list.count() == 1
        assert not dialog.restore_button.isEnabled()
        dialog.card_list.item(0).setSelected(True)
        assert dialog.restore_button.isEnabled()

        dialog.restore_selected()

        assert dialog.card_list.count() == 0
        assert store.get(card.id) is not None


def test_image_is_removed_only_after_last_card_reference_is_deleted(tmp_path) -> None:
    image = tmp_path / "capture.png"
    image.write_bytes(b"image")
    with CardStore(tmp_path / "cards.sqlite3") as store:
        first = store.add(Card(None, CardKind.IMAGE, "Game", "First", image_path=str(image)))
        second = store.add(Card(None, CardKind.IMAGE, "Game", "Second", image_path=str(image)))
        assert store.move_to_trash(first.id)
        deleted_first = store.get_deleted(first.id)
        assert deleted_first is not None
        assert store.delete_permanently(first.id)
        assert not remove_card_image_if_unused(store, deleted_first, tmp_path)
        assert image.is_file()

        assert store.move_to_trash(second.id)
        deleted_second = store.get_deleted(second.id)
        assert deleted_second is not None
        assert store.delete_permanently(second.id)
        assert remove_card_image_if_unused(store, deleted_second, tmp_path)
        assert not image.exists()


def test_image_outside_capture_directory_is_never_removed(tmp_path) -> None:
    captures = tmp_path / "captures"
    captures.mkdir()
    external = tmp_path / "keep.png"
    external.write_bytes(b"image")
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(Card(None, CardKind.IMAGE, "Game", "External", image_path=str(external)))
        assert store.move_to_trash(card.id)
        deleted = store.get_deleted(card.id)
        assert deleted is not None
        assert store.delete_permanently(card.id)

        assert not remove_card_image_if_unused(store, deleted, captures)
        assert external.is_file()
