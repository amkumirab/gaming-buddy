from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gaming_buddy.models import Card, CardKind
from gaming_buddy.pin import PinWidget


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _pin(
    card: Card,
    layout_updates: list[tuple[int, int]],
    collapsed_updates: list[bool],
) -> PinWidget:
    return PinWidget(
        card,
        lambda updated: layout_updates.append((updated.width, updated.height)),
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda updated: collapsed_updates.append(updated.collapsed),
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
    )


def test_collapsing_preserves_expanded_height_and_hides_body(
    application: QApplication,
) -> None:
    layouts: list[tuple[int, int]] = []
    collapsed_updates: list[bool] = []
    card = Card(1, CardKind.NOTE, "Control", "Code", content="0421", height=260)
    pin = _pin(card, layouts, collapsed_updates)

    pin.set_collapsed(True)

    assert card.collapsed is True
    assert card.height == 260
    assert pin.height() == PinWidget.COLLAPSED_HEIGHT
    assert pin._body.isHidden()
    assert pin._grip.isHidden()
    assert layouts[-1] == (card.width, 260)
    assert collapsed_updates == [True]
    pin.close()


def test_expanding_restores_saved_height_and_respects_lock(
    application: QApplication,
) -> None:
    layouts: list[tuple[int, int]] = []
    collapsed_updates: list[bool] = []
    card = Card(
        2,
        CardKind.NOTE,
        "General",
        "Map",
        height=280,
        locked=True,
        collapsed=True,
    )
    pin = _pin(card, layouts, collapsed_updates)

    assert pin.height() == PinWidget.COLLAPSED_HEIGHT
    pin.set_collapsed(False)

    assert card.collapsed is False
    assert pin.height() == 280
    assert not pin._body.isHidden()
    assert pin._grip.isHidden()
    assert collapsed_updates == [False]

    pin.set_locked(False, notify=False)
    assert not pin._grip.isHidden()
    pin.close()


def test_header_controls_toggle_collapsed_state(application: QApplication) -> None:
    collapsed_updates: list[bool] = []
    pin = _pin(
        Card(3, CardKind.NOTE, "General", "Route", content="Take the lift"),
        [],
        collapsed_updates,
    )
    pin.show()

    pin._collapse_button.click()
    assert pin.card.collapsed is True

    QTest.mouseDClick(pin._header, Qt.MouseButton.LeftButton)
    assert pin.card.collapsed is False
    assert collapsed_updates == [True, False]
    pin.close()
