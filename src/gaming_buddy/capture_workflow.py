from __future__ import annotations

from enum import StrEnum


class CaptureAction(StrEnum):
    SAVE_AND_PIN = "save_and_pin"
    SAVE_ONLY = "save_only"
    REVIEW = "review"


DEFAULT_CAPTURE_ACTION = CaptureAction.SAVE_AND_PIN
DEFAULT_CAPTURE_DELAY_SECONDS = 0
DEFAULT_KEEP_PANEL_HIDDEN = True
DEFAULT_CAPTURE_NOTIFICATIONS = True
CAPTURE_DELAY_OPTIONS = (0, 3, 5)


def normalize_capture_action(value: object) -> CaptureAction:
    try:
        return CaptureAction(str(value))
    except ValueError:
        return DEFAULT_CAPTURE_ACTION


def normalize_capture_delay(value: object) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CAPTURE_DELAY_SECONDS
    return seconds if seconds in CAPTURE_DELAY_OPTIONS else DEFAULT_CAPTURE_DELAY_SECONDS


def capture_start_delay_ms(seconds: int) -> int:
    normalized = normalize_capture_delay(seconds)
    return normalized * 1000 if normalized else 180
