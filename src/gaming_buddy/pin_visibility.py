from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class PinVisibilityController(QObject):
    auto_hide_requested = Signal()
    auto_restore_requested = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        delay_ms: int = 900,
    ) -> None:
        super().__init__(parent)
        self.enabled = False
        self.game_is_focused = False
        self.manually_hidden = False
        self.automatically_hidden = False
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(max(0, delay_ms))
        self.hide_timer.timeout.connect(self._apply_auto_hide)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.hide_timer.stop()
        if not enabled:
            if self.automatically_hidden:
                self.automatically_hidden = False
                if not self.manually_hidden:
                    self.auto_restore_requested.emit()
            return
        if not self.game_is_focused and not self.manually_hidden:
            self.hide_timer.start()

    def update_focus(self, game_is_focused: bool) -> None:
        self.game_is_focused = game_is_focused
        self.hide_timer.stop()
        if not self.enabled:
            return
        if game_is_focused:
            if self.automatically_hidden:
                self.automatically_hidden = False
                if not self.manually_hidden:
                    self.auto_restore_requested.emit()
            return
        if not self.manually_hidden and not self.automatically_hidden:
            self.hide_timer.start()

    def manual_show(self) -> None:
        self.hide_timer.stop()
        self.manually_hidden = False
        self.automatically_hidden = False

    def manual_hide(self) -> None:
        self.hide_timer.stop()
        self.manually_hidden = True
        self.automatically_hidden = False

    def _apply_auto_hide(self) -> None:
        if (
            not self.enabled
            or self.game_is_focused
            or self.manually_hidden
            or self.automatically_hidden
        ):
            return
        self.automatically_hidden = True
        self.auto_hide_requested.emit()
