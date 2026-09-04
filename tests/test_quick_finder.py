from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gaming_buddy.models import Card, CardKind
from gaming_buddy.quick_finder import (
    QuickFinderDialog,
    card_statuses,
    find_cards,
    updated_search_history,
)


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_active_game_and_general_cards_are_ranked_first() -> None:
    cards = [
        Card(1, CardKind.NOTE, "Other Game", "Map route", content="Exact title"),
        Card(2, CardKind.NOTE, "General", "Fast travel", content="Map marker"),
        Card(3, CardKind.IMAGE, "Control", "Maintenance", content="Basement map"),
    ]

    matches = find_cards(cards, "map", "Control")

    assert [card.id for card in matches] == [3, 2, 1]


def test_search_matches_multiple_terms_across_card_fields() -> None:
    cards = [
        Card(1, CardKind.NOTE, "Control", "Oceanview code", content="Turn left"),
        Card(2, CardKind.NOTE, "Control", "Oceanview map", content="Hotel lobby"),
    ]

    matches = find_cards(cards, "oceanview left")

    assert [card.id for card in matches] == [1]


def test_search_matches_card_tags() -> None:
    cards = [
        Card(1, CardKind.NOTE, "Control", "Route", content="Turn left"),
        Card(2, CardKind.IMAGE, "Control", "Arena", tags=("boss", "map")),
    ]

    assert [card.id for card in find_cards(cards, "boss")] == [2]


def test_card_statuses_describe_workspace_state() -> None:
    card = Card(
        1,
        CardKind.IMAGE,
        "Control",
        "Map",
        pinned=True,
        locked=True,
        collapsed=True,
    )

    assert card_statuses(card) == ["Image", "Pinned", "Locked", "Collapsed"]

    library_card = Card(
        2,
        CardKind.NOTE,
        "Control",
        "Old layout",
        locked=True,
        collapsed=True,
    )
    assert card_statuses(library_card) == ["Note"]


def test_search_history_is_recent_unique_and_bounded() -> None:
    history = ["map", "Boss", "MAP", "route", "code", "build"]

    assert updated_search_history(history, " MAP ") == [
        "MAP",
        "Boss",
        "route",
        "code",
        "build",
    ]
    assert updated_search_history(history, "", limit=3) == ["map", "Boss", "route"]


def test_dialog_supports_keyboard_selection_and_activation(
    application: QApplication,
) -> None:
    cards = [
        Card(1, CardKind.NOTE, "Control", "First map", content="Lobby"),
        Card(2, CardKind.NOTE, "Control", "Second map", content="Basement"),
    ]
    dialog = QuickFinderDialog(cards, "Control", ["map"])
    activated: list[tuple[int | None, str]] = []
    dialog.card_activated.connect(
        lambda card, query: activated.append((card.id, query))
    )
    dialog.show()
    application.processEvents()

    QTest.keyClicks(dialog.search, "map")
    assert dialog.results.count() == 2
    assert dialog.results.currentRow() == 0

    QTest.keyClick(dialog.search, Qt.Key.Key_Down)
    assert dialog.results.currentRow() == 1
    QTest.keyClick(dialog.results, Qt.Key.Key_Return)

    assert activated == [(2, "map")]
    dialog.close()


def test_recent_search_selection_populates_query(application: QApplication) -> None:
    dialog = QuickFinderDialog([], recent_searches=["safe code", "boss route"])

    dialog.recent.setCurrentIndex(2)

    assert dialog.search.text() == "boss route"
    dialog.close()


def test_image_result_tooltip_includes_extracted_text(application: QApplication) -> None:
    card = Card(
        7,
        CardKind.IMAGE,
        "Resident Evil 2",
        "West office safe",
        content="Left 9, right 15, left 7",
        image_path="safe.png",
    )
    dialog = QuickFinderDialog([card])

    tooltip = dialog.results.item(0).toolTip()

    assert "right 15" in tooltip
    assert "safe.png" in tooltip
    dialog.close()
