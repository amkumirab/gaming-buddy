"""Run the real app against disposable data and quit through its normal action."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

import gaming_buddy.app as app_module
import gaming_buddy.updates as update_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.paths import ensure_data_dirs
from gaming_buddy.text_recognition import RecognitionResult
from gaming_buddy.text_recognition_dialog import TextRecognitionDialog
from gaming_buddy.updates import ReleaseAsset, ReleaseInfo, UpdateCancelled, UpdateError

root = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "normal"
started = threading.Event()
release_worker = threading.Event()
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
    QSettings.setPath(QSettings.Format.IniFormat, scope, str(root / "settings"))
settings = QSettings("GamingBuddy", "GamingBuddy")
settings.setValue("onboarding/completed", True)
settings.setValue("updates/automatic_checks", False)
settings.sync()
app_module.ensure_data_dirs = lambda: ensure_data_dirs(root / "data")


def blocked_recognition(_path, language):
    started.set()
    if not release_worker.wait(5):
        raise TimeoutError("Runtime test did not release recognition")
    return RecognitionResult("Screenshot clue", language)


def blocked_check():
    started.set()
    if not release_worker.wait(5):
        raise TimeoutError("Runtime test did not release update check")
    raise UpdateError("Controlled offline response")


def blocked_download(_release, _destination, *, cancelled, **kwargs):
    started.set()
    if not release_worker.wait(5):
        raise TimeoutError("Runtime test did not release download")
    assert cancelled.is_set(), "Quit must request cooperative download cancellation"
    raise UpdateCancelled("Update download cancelled.")


update_module.fetch_latest_release = blocked_check
update_module.download_release = blocked_download


class ObservedDashboard(Dashboard):
    def __init__(self, *args):
        super().__init__(*args)
        QTimer.singleShot(500, self.report_ready)
        QTimer.singleShot(15000, self.quit_app)

    def report_ready(self):
        print(
            "READY" if self.shortcut_status() and self.tray.isVisible() else "NOT_READY", flush=True
        )
        if mode == "quick_panel":
            self.show_quick_panel()
            panel = self.quick_panel.panel
            assert panel.isVisible() and not self.isVisible()
            panel.note_button.click()
            panel.note_editor.setPlainText("Quick panel exit clue")
            print("QUICK_VISIBLE", flush=True)
            QTimer.singleShot(100, self.quit_app)
            return
        if mode != "normal":
            self.note_input.setPlainText("Busy exit clue")
            self.settings.setValue("capture/delay_seconds", 3)
            self.settings.setValue("capture/notifications", False)
            self.start_capture()
            if mode == "check":
                assert self.update_controller.check_for_updates()
            elif mode == "download":
                asset = ReleaseAsset("setup.exe", "https://example.test/setup.exe", 1)
                info = ReleaseInfo("99.0.0", "v99.0.0", "Test", "", "", "", asset, asset)
                assert self.update_controller.download_update(info, root / "updates")
            elif mode == "recognition":
                self._text_recognition_dialog = TextRecognitionDialog(
                    root / "clue.png", "", [], self.game_input.text(), self,
                    recognizer=blocked_recognition, auto_start=False,
                )
                self._text_recognition_dialog.start_recognition()
            self._busy_timer = QTimer(self)
            self._busy_timer.setInterval(10)
            self._busy_timer.timeout.connect(self.quit_when_busy)
            self._busy_timer.start()

    def quit_when_busy(self):
        if not started.is_set():
            return
        self._busy_timer.stop()
        self.quit_app()
        print("WAITING" if self.shutdown_controller.active else "PREMATURE", flush=True)
        QTimer.singleShot(0, self.release_from_gui)

    def release_from_gui(self):
        assert self._quitting and not self._really_quit
        assert self.store.list() == []
        print("RESPONSIVE", flush=True)
        release_worker.set()

    def show_panel(self):
        super().show_panel()
        print("ACTIVATED", flush=True)
        QTimer.singleShot(100, self.quit_app)


app_module.Dashboard = ObservedDashboard
raise SystemExit(app_module.main())
