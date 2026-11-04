from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

import gaming_buddy.pin as pin_module
from gaming_buddy.models import Card, CardKind
from gaming_buddy.pin import PinWidget


@pytest.mark.parametrize("area,position", [
    (QRect(0, 0, 1920, 1040), (80, 960)),
    (QRect(-1280, -720, 1280, 680), (-1200, -120)),
])
def test_restored_collapsed_header_keeps_saved_position_and_expanded_size(
    qt_application, monkeypatch, area, position,
):
    screen = SimpleNamespace(availableGeometry=lambda: QRect(area))
    monkeypatch.setattr(pin_module.QGuiApplication, "screens", lambda: [screen])
    monkeypatch.setattr(pin_module.QGuiApplication, "primaryScreen", lambda: screen)
    card = Card(1, CardKind.NOTE, "Puzzle", "Code", content="0451", x=position[0], y=position[1],
                width=320, height=260, collapsed=True, locked=True)
    noop = lambda *_: None
    pin = PinWidget(card, *([noop] * 11))
    try:
        assert (pin.x(), pin.y()) == position
        assert pin.height() == PinWidget.COLLAPSED_HEIGHT
        assert card.height == 260
        assert area.contains(pin.geometry())
        pin.set_collapsed(False)
        assert area.contains(pin.geometry())
        assert card.locked and not card.collapsed
        assert pin.height() == 260
    finally:
        pin.discard_pending_layout()
        pin.close()
        pin.deleteLater()
