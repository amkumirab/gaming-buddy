from __future__ import annotations

from dataclasses import dataclass

MAX_PRESET_NAME_LENGTH = 48


def normalize_preset_name(value: str) -> str:
    name = " ".join(value.split())
    if not name:
        raise ValueError("Enter a layout name.")
    if len(name) > MAX_PRESET_NAME_LENGTH:
        raise ValueError(
            f"Layout names can contain up to {MAX_PRESET_NAME_LENGTH} characters."
        )
    return name


@dataclass(frozen=True, slots=True)
class PresetPinLayout:
    card_id: int
    visible: bool
    x: int
    y: int
    width: int
    height: int
    opacity: float
    locked: bool
    collapsed: bool


@dataclass(frozen=True, slots=True)
class WorkspacePresetSummary:
    id: int
    game: str
    name: str
    pin_count: int
    active: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class WorkspacePreset:
    id: int
    game: str
    name: str
    pins: tuple[PresetPinLayout, ...]
    active: bool
    created_at: str
    updated_at: str
