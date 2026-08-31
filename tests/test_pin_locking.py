from __future__ import annotations

import pytest
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


def _pin(card: Card, lock_updates: list[bool]) -> PinWidget:
    return PinWidget(
        card,
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda updated: lock_updates.append(updated.locked),
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
        lambda _card: None,
    )


def test_lock_hides_resize_grip_and_notifies_storage(
    application: QApplication,
) -> None:
    updates: list[bool] = []
    card = Card(1, CardKind.NOTE, "Control", "Code", content="0421")
    pin = _pin(card, updates)

    assert not pin._grip.isHidden()
    assert pin._lock_indicator.isHidden()

    pin.set_locked(True)

    assert card.locked is True
    assert pin._grip.isHidden()
    assert not pin._lock_indicator.isHidden()
    assert updates == [True]
    pin.close()


def test_restored_locked_pin_can_be_unlocked_without_duplicate_notification(
    application: QApplication,
) -> None:
    updates: list[bool] = []
    card = Card(2, CardKind.NOTE, "General", "Map", locked=True)
    pin = _pin(card, updates)

    assert pin._grip.isHidden()
    assert not pin._lock_indicator.isHidden()
    assert updates == []

    pin.set_locked(False, notify=False)

    assert card.locked is False
    assert not pin._grip.isHidden()
    assert pin._lock_indicator.isHidden()
    assert updates == []
    pin.close()
