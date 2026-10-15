"""Keep the event loop running until background tasks have really stopped."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal


class ShutdownController(QObject):
    finished = Signal()
    cancelled = Signal()
    timed_out = Signal()

    def __init__(
        self, is_ready: Callable[[], bool], parent: QObject | None = None, *,
        timeout_ms: int = 60_000, poll_ms: int = 50,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        if timeout_ms <= 0 or poll_ms <= 0:
            raise ValueError("Shutdown intervals must be positive")
        self._is_ready = is_ready
        self._clock = clock
        self._timeout = timeout_ms / 1000
        self._deadline = 0.0
        self.active = False
        self._finished = False
        self._timer = QTimer(self)
        self._timer.setInterval(poll_ms)
        self._timer.timeout.connect(self._poll)

    def request(self) -> None:
        if self.active or self._finished:
            return
        self.active = True
        self._deadline = self._clock() + self._timeout
        # QTimer polling keeps queued results and worker cleanup moving on the GUI thread.
        # https://doc.qt.io/qtforpython-6/PySide6/QtCore/QTimer.html
        self._timer.start()
        self._poll()

    def cancel(self) -> None:
        if not self.active and not self._finished:
            return
        self._timer.stop()
        self.active = False
        self._finished = False
        self.cancelled.emit()

    def _poll(self) -> None:
        if not self.active:
            return
        if self._is_ready():
            self._timer.stop()
            self.active = False
            self._finished = True
            self.finished.emit()
        elif self._clock() >= self._deadline:
            self._timer.stop()
            self.active = False
            self.timed_out.emit()
