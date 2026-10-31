from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPoint, QSignalBlocker, Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from gaming_buddy.quick_panel import QuickPanel

if TYPE_CHECKING:
    from gaming_buddy.dashboard import Dashboard


class QuickPanelController(QObject):
    def __init__(self, dashboard: Dashboard) -> None:
        super().__init__(dashboard)
        self.dashboard = dashboard
        self.panel: QuickPanel | None = None
        self._capture_origin = False
        dashboard.installEventFilter(self)
        dashboard.note_input.textChanged.connect(self.sync_draft)
        dashboard.game_input.textChanged.connect(self._sync_game)
        dashboard.statusBar().messageChanged.connect(self._status)
        dashboard.shutdown_started.connect(self._shutdown_started)
        dashboard.shutdown_cancelled.connect(self._shutdown_cancelled)

    def _allowed(self) -> bool:
        host = self.dashboard
        return not (host._quitting or host._capture_in_progress
                    or host._card_pack_dialog is not None or QApplication.activeModalWidget())

    def show(self) -> None:
        if not self._allowed():
            return
        host = self.dashboard
        host.game_detector.poll_now()
        if self.panel is None:
            panel = self.panel = QuickPanel(host)
            panel.installEventFilter(self)
            panel.capture_requested.connect(host.start_capture)
            panel.find_requested.connect(self._find)
            panel.full_panel_requested.connect(self._full_panel)
            panel.save_requested.connect(self._save_note)
            panel.note_editor.textChanged.connect(self._draft_edited)
            panel.hidden.connect(self._remember_position)
        panel = self.panel
        self.sync_draft()
        self._sync_game(host.game_input.text())
        if not panel.isVisible():
            position = host.settings.value("quick_panel/position")
            if isinstance(position, QPoint):
                panel.move(position)
            else:
                screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
                if screen is not None:
                    panel.move(screen.availableGeometry().center() - panel.rect().center())
        host.hide()
        panel.show()
        self._fit_to_screen()
        panel.raise_()
        panel.activateWindow()
        (panel.note_editor if panel.note_button.isChecked() else panel.capture_button).setFocus(
            Qt.FocusReason.ShortcutFocusReason
        )

    def toggle(self) -> None:
        if self.panel is not None and self.panel.isVisible():
            self.hide()
        else:
            self.show()

    def hide(self) -> None:
        if self.panel is not None:
            self.panel.hide()

    def sync_draft(self) -> None:
        if self.panel is None:
            return
        editor = self.panel.note_editor
        text = self.dashboard.note_input.toPlainText()
        if editor.toPlainText() != text:
            blocker = QSignalBlocker(editor)
            editor.setPlainText(text)
            del blocker

    def _draft_edited(self) -> None:
        if self.panel is not None and not self.dashboard._quitting:
            self.dashboard.note_input.setPlainText(self.panel.note_editor.toPlainText())

    def _sync_game(self, game: str) -> None:
        if self.panel is not None:
            self.panel.set_game(game)

    def _status(self, message: str) -> None:
        if self.panel is not None:
            self.panel.show_status(message)

    def _save_note(self, pin: bool) -> None:
        if not self._allowed() or self.panel is None:
            return
        if not self.dashboard.note_input.toPlainText().strip():
            self.panel.show_status("Write a note first.")
            return
        (self.dashboard.pin_note if pin else self.dashboard.save_note)()
        self.sync_draft()
        self.panel.show_status(
            "Note not saved. Your draft is still available."
            if self.dashboard.note_input.toPlainText().strip()
            else ("Note saved and pinned." if pin else "Note saved.")
        )

    def _find(self) -> None:
        if self._allowed():
            self.dashboard.show_quick_finder()
            self.hide()

    def _full_panel(self) -> None:
        if self._allowed():
            self.hide()
            self.dashboard.show_panel()

    def capture_started(self) -> None:
        self._capture_origin = self.panel is not None and self.panel.isVisible()
        self.hide()

    def capture_finished(self, *, restore: bool) -> bool:
        originated_here = self._capture_origin
        self._capture_origin = False
        if originated_here and restore and not self.dashboard._quitting:
            self.show()
            return True
        return False

    def _shutdown_started(self) -> None:
        self._capture_origin = False
        if self.panel is not None:
            self.panel.setEnabled(False)
            self.hide()

    def _shutdown_cancelled(self) -> None:
        if self.panel is not None:
            self.panel.setEnabled(True)

    def _remember_position(self) -> None:
        if self.panel is not None:
            self.dashboard.settings.setValue("quick_panel/position", self.panel.pos())

    def _fit_to_screen(self) -> None:
        panel = self.panel
        if panel is None:
            return
        frame = panel.frameGeometry()
        screen = QGuiApplication.screenAt(frame.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        left = max(area.left(), min(frame.left(), area.right() - frame.width() + 1))
        top = max(area.top(), min(frame.top(), area.bottom() - frame.height() + 1))
        panel.move(panel.pos() + QPoint(left - frame.left(), top - frame.top()))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.dashboard and event.type() == QEvent.Type.Show:
            self.hide()
        elif (watched is self.panel and event.type() == QEvent.Type.Resize
              and self.panel.isVisible()):
            self._fit_to_screen()
        return super().eventFilter(watched, event)
