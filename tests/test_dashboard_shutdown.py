from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QMessageBox

import gaming_buddy.dashboard as dashboard_module
import gaming_buddy.updates as updates_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.note_drafts import DraftError
from gaming_buddy.storage import CardStore
from gaming_buddy.updates import UpdateError


@pytest.fixture
def panel(qt_application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    settings.setValue("capture/delay_seconds", 3)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    store = CardStore(tmp_path / "cards.sqlite3")
    dashboard = Dashboard(store, tmp_path / "captures")
    qt_application.processEvents()
    yield dashboard
    if hasattr(dashboard, "shutdown_controller"):
        dashboard.shutdown_controller.cancel()
    dashboard.note_draft_timer.stop()
    dashboard.game_detector.stop()
    dashboard.tray.hide()
    dashboard._really_quit = True
    dashboard.close()
    store.close()


@pytest.fixture
def busy_check(panel, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    workers = []

    def fetch():
        workers.append(threading.current_thread())
        started.set()
        release.wait(3)
        raise UpdateError("Test response unavailable")

    monkeypatch.setattr(updates_module, "fetch_latest_release", fetch)
    assert panel.update_controller.check_for_updates()
    assert started.wait(3)
    yield release
    release.set()
    for worker in workers:
        worker.join(3)
        assert not worker.is_alive()


def wait_for_exit(signal):
    if signal.count() == 0:
        assert signal.wait(3000), "Exit did not complete after the worker finished"
    assert signal.count() == 1


def test_busy_exit_waits_and_saves_draft_only_before_final_quit(panel, busy_check, monkeypatch):
    exits = []
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    exited = QSignalSpy(panel.request_quit)
    panel.note_input.setPlainText("Unsaved multi-line note\nKeep this clue")
    panel.quit_app()
    panel.quit_app()
    assert exited.count() == 0
    assert panel.store.list() == []  # Storage must remain usable throughout the wait.
    assert panel._shutdown_progress.labelText().startswith("Finishing tasks")
    busy_check.set()
    wait_for_exit(exited)
    assert exits == [True]
    assert panel.note_draft_store.load().text == "Unsaved multi-line note\nKeep this clue"


def test_cancel_exit_restores_admission_and_does_not_quit(panel, busy_check, monkeypatch):
    exits = []
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    cancelled = QSignalSpy(panel.shutdown_cancelled)
    panel.quit_app()
    panel.shutdown_controller.cancel()
    assert cancelled.count() == 1
    assert not panel._quitting
    assert panel._shutdown_progress is None
    assert exits == []
    panel.start_capture()
    assert panel._capture_in_progress


def test_quit_cancels_pending_capture_and_blocks_late_screenshot(panel, busy_check, monkeypatch):
    opens = []
    monkeypatch.setattr(dashboard_module, "begin_capture", lambda: opens.append(True))
    panel.start_capture()
    panel.quit_app()
    assert not panel._capture_in_progress
    assert not panel._capture_timer.isActive()
    panel._open_capture_overlay()  # A queued callback must also be harmless.
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    panel._save_capture(image)
    assert opens == []
    assert panel.store.list() == []
    assert not list(panel.captures_dir.glob("*.png"))


def test_update_failure_during_quit_does_not_open_a_modal_warning(
    panel, busy_check, monkeypatch,
):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    panel._update_check_manual = True
    panel.quit_app()
    panel._on_update_check_failed("Late update failure")
    panel._on_update_download_failed("Late download failure")
    assert warnings == []


def test_quitting_during_capture_review_cannot_save_after_review_returns(
    panel, busy_check, monkeypatch,
):
    panel.settings.setValue("capture/action", "review")

    def review(_image):
        panel.quit_app()
        return True

    monkeypatch.setattr(panel, "_review_capture", review)
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    panel._save_capture(image)
    assert panel.store.list() == []


def test_failed_draft_save_keeps_app_open_and_allows_exit_retry(panel, monkeypatch):
    exits = []
    warnings = []
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    save = panel.note_draft_store.save
    panel.note_input.setPlainText("Keep this unsaved clue")

    def fail(*_args):
        raise DraftError("Draft folder is unavailable")

    monkeypatch.setattr(panel.note_draft_store, "save", fail)
    panel.quit_app()
    assert exits == []
    assert not panel._quitting
    assert not panel._really_quit
    assert panel.note_input.toPlainText() == "Keep this unsaved clue"
    assert warnings
    monkeypatch.setattr(panel.note_draft_store, "save", save)
    panel.quit_app()
    assert exits == [True]


def test_installer_starts_only_after_background_work_finishes(panel, busy_check, monkeypatch):
    launched = []
    monkeypatch.setattr(QApplication, "quit", lambda: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(
        dashboard_module.QProcess, "startDetached",
        lambda path, _args: launched.append(path) or True,
    )
    finished = QSignalSpy(panel.request_quit)
    panel._on_update_download_ready("verified-setup.exe", SimpleNamespace(version="0.2.0"))
    assert launched == []
    busy_check.set()
    wait_for_exit(finished)
    assert launched == ["verified-setup.exe"]


def test_capture_started_before_exit_is_closed_if_shutdown_begins_inside_grab(
    panel, busy_check, monkeypatch,
):
    closed = []

    def begin():
        panel.quit_app()
        return SimpleNamespace(close=lambda: closed.append(True))

    monkeypatch.setattr(dashboard_module, "begin_capture", begin)
    panel._open_capture_overlay()
    assert closed == [True]
    assert panel.capture_overlay is None


def test_cancel_exit_resumes_pending_draft_and_undo_timers(panel, busy_check):
    panel.note_input.setPlainText("Autosave after cancelled exit")
    panel.undo_timer.start(10_000)
    assert panel.note_draft_timer.isActive()
    panel.quit_app()
    assert not panel.note_draft_timer.isActive()
    assert not panel.undo_timer.isActive()
    panel.shutdown_controller.cancel()
    assert panel.note_draft_timer.isActive()
    assert panel.undo_timer.isActive()


def test_late_recognition_request_cannot_start_a_new_dialog(panel, busy_check, monkeypatch):
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    panel.captures_dir.mkdir(exist_ok=True)
    path = panel.captures_dir / "clue.png"
    assert image.save(str(path))
    card = Card(1, CardKind.IMAGE, "Game", "Clue", image_path=str(path))
    panel._recognition_languages = [SimpleNamespace(tag="en-US", display_name="English")]

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError("A new recognition dialog started during shutdown")

    monkeypatch.setattr(dashboard_module, "TextRecognitionDialog", unexpected_dialog)
    panel.quit_app()
    panel._extract_image_text(card)
    assert panel._text_recognition_dialog is None


def test_timeout_cancels_exit_without_terminating_a_live_task(panel, busy_check, monkeypatch):
    exits = []
    warnings = []
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    panel.quit_app()
    panel.shutdown_controller._deadline = 0
    panel.shutdown_controller._poll()
    assert not panel._quitting
    assert not panel.update_controller.shutdown_ready
    assert panel._shutdown_progress is None
    assert exits == []
    assert warnings


def test_failed_installer_launch_keeps_app_open(panel, monkeypatch):
    exits = []
    warnings = []
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    monkeypatch.setattr(dashboard_module.QProcess, "startDetached", lambda *args: (False, 0))
    panel._on_update_download_ready("verified-setup.exe", SimpleNamespace(version="0.2.0"))
    assert exits == []
    assert not panel._quitting
    assert panel._pending_installer is None
    assert warnings


def test_cancelled_exit_discards_pending_installer_launch(panel, busy_check, monkeypatch):
    launched = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(
        dashboard_module.QProcess, "startDetached",
        lambda path, _args: launched.append(path) or True,
    )
    panel._on_update_download_ready("verified-setup.exe", SimpleNamespace(version="0.2.0"))
    panel.shutdown_controller.cancel()
    assert not panel._quitting
    assert panel._pending_installer is None
    assert launched == []


def test_pin_layout_save_failure_keeps_app_open(panel, monkeypatch):
    import sqlite3

    exits = []
    warnings = []
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))

    def failed_save():
        raise sqlite3.OperationalError("Data folder unavailable")

    panel.pins[1] = SimpleNamespace(save_now=failed_save)
    try:
        panel.quit_app()
        assert exits == []
        assert not panel._quitting
        assert warnings
    finally:
        panel.pins.clear()
