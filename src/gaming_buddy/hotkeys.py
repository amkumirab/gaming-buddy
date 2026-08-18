from __future__ import annotations

from pynput import keyboard
from PySide6.QtCore import QObject, Signal


class GlobalHotkeys(QObject):
    toggle_panel = Signal()
    capture_area = Signal()
    toggle_click_through = Signal()
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        try:
            self._listener = keyboard.GlobalHotKeys(
                {
                    "<ctrl>+<shift>+g": self.toggle_panel.emit,
                    "<ctrl>+<shift>+s": self.capture_area.emit,
                    "<ctrl>+<shift>+l": self.toggle_click_through.emit,
                }
            )
            self._listener.start()
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - platform hook errors vary
            self.failed.emit(str(exc))

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
