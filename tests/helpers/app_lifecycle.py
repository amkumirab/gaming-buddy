"""Run the real app against disposable data and quit through its normal action."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QImage

import gaming_buddy.app as app_module
import gaming_buddy.dashboard as dashboard_module
import gaming_buddy.updates as update_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.paths import ensure_data_dirs
from gaming_buddy.text_recognition import RecognitionLanguage, RecognitionResult
from gaming_buddy.text_recognition_dialog import TextRecognitionDialog
from gaming_buddy.updates import ReleaseAsset, ReleaseInfo, UpdateCancelled, UpdateError

root = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "normal"
started = threading.Event()
release_worker = threading.Event()
settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
settings.setFallbacksEnabled(False)
dashboard_module.QSettings = lambda *_: settings
settings.setValue("onboarding/completed", mode != "walkthrough")
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


def capture_text_languages():
    if mode == "capture_text_busy":
        started.set()
        if not release_worker.wait(5):
            raise TimeoutError("Runtime test did not release language discovery")
    return [RecognitionLanguage("en-US", "English")]


if mode.startswith("capture_text"):
    dashboard_module.available_languages = capture_text_languages
    dashboard_module.TextRecognitionDialog = lambda *args, **kwargs: TextRecognitionDialog(
        *args, **kwargs,
        recognizer=lambda _, language: RecognitionResult("Code 0451", language),
    )


class ObservedDashboard(Dashboard):
    def __init__(self, *args):
        super().__init__(*args)
        QTimer.singleShot(500, self.report_ready)
        QTimer.singleShot(15000, self.quit_app)

    def report_ready(self):
        assert Path(self.settings.fileName()).resolve() == (root / "settings.ini").resolve()
        print(
            "READY" if self.shortcut_status() and self.tray.isVisible() else "NOT_READY", flush=True
        )
        if mode.startswith("capture_text"):
            self.settings.setValue("capture/action", "review")
            self.settings.setValue("capture/notifications", False)
            self.show_quick_panel()
            self.quick_panel.panel.capture_button.text_action.trigger()
            self._capture_timer.stop()
            image = QImage(320, 180, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.blue)
            self._save_capture(image)
            assert self._text_recognition_dialog.isVisible()
            print("CAPTURE_TEXT_READY", flush=True)
            if mode == "capture_text_busy":
                self.note_input.setPlainText("Capture text draft")
                self.watch_busy_exit()
            else:
                self._text_recognition_dialog.work_finished.connect(self.save_capture_text)
            return
        if mode in ("walkthrough", "walkthrough_resume"):
            assert self.walkthrough_panel.isVisible()
            if mode == "walkthrough":
                assert self.walkthrough.progress.step == 0
                self.note_input.setPlainText("My first clue\n\nKeep this note")
                self.save_note()
                assert self.walkthrough.progress.step == 1
            else:
                assert self.walkthrough.progress.step == 1
                self.walkthrough_panel.action_button.click()
                assert self.walkthrough.progress.step == 2
                self.show_quick_panel()
                assert self.quick_panel.panel.isVisible()
            print("WALKTHROUGH_OK", flush=True)
            QTimer.singleShot(100, self.quit_app)
            return
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
            self.watch_busy_exit()

    def save_capture_text(self):
        dialog = self._text_recognition_dialog
        assert dialog.shutdown_ready
        dialog.text.setPlainText("Reviewed code\n0451")
        dialog.accept()
        assert self._text_recognition_dialog is None
        print("CAPTURE_TEXT_SAVED", flush=True)
        QTimer.singleShot(100, self.quit_app)

    def watch_busy_exit(self):
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
        cards = self.store.list()
        if mode == "capture_text_busy":
            assert len(cards) == 1 and cards[0].content == ""
        else:
            assert cards == []
        print("RESPONSIVE", flush=True)
        release_worker.set()

    def show_panel(self):
        super().show_panel()
        if not mode.startswith("walkthrough"):
            print("ACTIVATED", flush=True)
            QTimer.singleShot(100, self.quit_app)


app_module.Dashboard = ObservedDashboard
raise SystemExit(app_module.main())
