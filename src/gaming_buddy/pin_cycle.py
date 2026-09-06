from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CyclePosition:
    card_id: int
    position: int
    total: int


@dataclass(frozen=True, slots=True)
class CycleRestore:
    visibility: dict[int, bool]


class PinCycleState:
    """Track a temporary single-pin view and its original visibility."""

    def __init__(self) -> None:
        self.active = False
        self._card_ids: tuple[int, ...] = ()
        self._index = 0
        self._visibility: dict[int, bool] = {}

    @property
    def card_ids(self) -> tuple[int, ...]:
        return self._card_ids

    @property
    def current(self) -> CyclePosition | None:
        if not self.active or not self._card_ids:
            return None
        return CyclePosition(
            self._card_ids[self._index],
            self._index + 1,
            len(self._card_ids),
        )

    def enter(
        self,
        card_ids: Sequence[int],
        visibility: Mapping[int, bool],
        *,
        backwards: bool = False,
    ) -> CyclePosition | None:
        ordered_ids = tuple(dict.fromkeys(card_ids))
        if self.active or not ordered_ids:
            return None
        self.active = True
        self._card_ids = ordered_ids
        self._index = len(ordered_ids) - 1 if backwards else 0
        self._visibility = dict(visibility)
        return self.current

    def move(self, step: int) -> CyclePosition | None:
        if not self.active or not self._card_ids:
            return None
        self._index = (self._index + step) % len(self._card_ids)
        return self.current

    def leave(self) -> CycleRestore | None:
        if not self.active:
            return None
        restore = CycleRestore(dict(self._visibility))
        self.active = False
        self._card_ids = ()
        self._index = 0
        self._visibility.clear()
        return restore
