from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from gaming_buddy.bulk_card_dialog import BulkCardChanges, BulkCardDialog


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_bulk_dialog_collects_game_and_tag_changes(
    application: QApplication,
) -> None:
    dialog = BulkCardDialog(4, ["Control", "Elden Ring"])
    dialog.move_game.setChecked(True)
    dialog.game_input.setCurrentText("  Alan Wake 2  ")
    dialog.add_tags_input.setText("Boss, map, boss")
    dialog.remove_tags_input.setText("old route, obsolete")

    assert dialog.values() == BulkCardChanges(
        game="Alan Wake 2",
        add_tags=("Boss", "map"),
        remove_tags=("old route", "obsolete"),
    )


def test_bulk_dialog_can_change_only_tags(application: QApplication) -> None:
    dialog = BulkCardDialog(2, [])
    dialog.add_tags_input.setText("puzzle")

    assert dialog.values() == BulkCardChanges(None, ("puzzle",), ())


def test_bulk_dialog_requires_a_change(application: QApplication) -> None:
    dialog = BulkCardDialog(2, [])

    with pytest.raises(ValueError, match="at least one change"):
        dialog.values()

    dialog.move_game.setChecked(True)
    with pytest.raises(ValueError, match="game name"):
        dialog.values()


def test_bulk_dialog_rejects_overlapping_tag_changes(
    application: QApplication,
) -> None:
    dialog = BulkCardDialog(2, [])
    dialog.add_tags_input.setText("Boss")
    dialog.remove_tags_input.setText("boss")

    with pytest.raises(ValueError, match="cannot be added and removed"):
        dialog.values()
