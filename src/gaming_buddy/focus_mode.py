from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PinPresentation:
    visible: bool
    opacity: float


@dataclass(frozen=True, slots=True)
class FocusRestore:
    panel_was_visible: bool
    pins: dict[int, PinPresentation]


class FocusModeState:
    """Track temporary presentation changes without altering saved card layout."""

    def __init__(self) -> None:
        self.active = False
        self._panel_was_visible = False
        self._pins: dict[int, PinPresentation] = {}

    def enter(
        self,
        *,
        panel_visible: bool,
        pins: Mapping[int, PinPresentation],
    ) -> bool:
        if self.active:
            return False
        self.active = True
        self._panel_was_visible = panel_visible
        self._pins = dict(pins)
        return True

    def remember_pin(self, card_id: int, presentation: PinPresentation) -> None:
        if self.active:
            self._pins.setdefault(card_id, presentation)

    def leave(self) -> FocusRestore | None:
        if not self.active:
            return None
        restore = FocusRestore(self._panel_was_visible, dict(self._pins))
        self.active = False
        self._panel_was_visible = False
        self._pins.clear()
        return restore
