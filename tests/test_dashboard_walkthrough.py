import sqlite3

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialog

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore
from gaming_buddy.walkthrough import WalkthroughProgress


@pytest.fixture
def host(qt_application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    settings.setValue("capture/notifications", False)
    settings.setValue("capture/action", "save_only")
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        dashboard = Dashboard(store, tmp_path / "captures")
        for timer in dashboard._startup_timers:
            timer.stop()
        yield dashboard
        dashboard.note_draft_timer.stop()
        dashboard._capture_timer.stop()
        dashboard.game_detector.stop()
        for pin in dashboard.pins.values():
            pin.discard_pending_layout()
            pin.close()
            pin.deleteLater()
        dashboard.tray.hide()
        dashboard._really_quit = True
        dashboard.close()
        dashboard.deleteLater()
        qt_application.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def capture(host):
    image = QImage(20, 15, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    host.start_capture()
    host._capture_timer.stop()
    host._save_capture(image)


def test_existing_users_not_interrupted_but_help_starts_walkthrough(host):
    host._show_first_run_setup()
    assert host.walkthrough.progress.paused
    host.show_getting_started()
    assert host.walkthrough_panel.isVisible()
    assert host.isVisible()
    assert host.walkthrough.progress.step == 0


def test_first_run_starts_nonmodal_and_resume_keeps_progress(host):
    host.settings.setValue("onboarding/completed", False)
    host.note_input.setPlainText("Existing draft\nKeep me")
    host._show_first_run_setup()
    assert not host.walkthrough.progress.paused
    host.walkthrough_panel.action_button.click()
    assert host.note_input.toPlainText() == "Existing draft\nKeep me"
    host.save_note()
    assert host.walkthrough.progress.step == 1
    host.walkthrough_panel.pause_button.click()
    assert host.walkthrough_panel.isHidden()
    assert WalkthroughProgress.load(host.settings).step == 1
    host.show_getting_started()
    assert host.walkthrough.progress.step == 1


def test_complete_real_note_pin_capture_and_quick_panel_flow(host):
    host.show_getting_started()
    host.note_input.setPlainText("A real clue\n\nDoor code: 1234")
    host.save_note()
    note = host.store.list()[0]
    assert host.walkthrough.progress.note_id == note.id
    host.walkthrough_panel.action_button.click()
    assert note.id in host.pins
    assert host.walkthrough.progress.step == 2
    capture(host)
    assert host.walkthrough.progress.step == 3
    assert len(host.store.list()) == 2
    host.walkthrough_panel.action_button.click()
    assert host.quick_panel.panel.isVisible()
    assert host.walkthrough.progress.step == 4
    host.show_panel()
    assert "4 completed" in host.walkthrough_panel.description.text()
    host.walkthrough_panel.pause_button.click()
    assert WalkthroughProgress.load(host.settings).paused
    assert host.store.get(note.id).content == "A real clue\n\nDoor code: 1234"


def test_save_and_pin_completes_both_note_steps(host):
    host.show_getting_started()
    host.note_input.setPlainText("Pin this clue")
    host.pin_note()
    assert host.walkthrough.progress.step == 2


def test_save_failure_does_not_advance_or_lose_draft(host, monkeypatch):
    host.show_getting_started()
    host.note_input.setPlainText("Disk full clue")
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)

    def fail(_):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(host.store, "add", fail)
    host.save_note()
    assert host.walkthrough.progress.step == 0
    assert host.note_input.toPlainText() == "Disk full clue"


def test_skip_summary_restart_and_later_do_not_touch_cards(host):
    host.show_getting_started()
    for _ in range(4):
        host.walkthrough_panel.skip_button.click()
    assert "0 completed" in host.walkthrough_panel.description.text()
    assert "4 skipped" in host.walkthrough_panel.description.text()
    host.note_input.setPlainText("Do not replace")
    host.walkthrough_panel.action_button.click()
    assert host.walkthrough.progress.step == 0
    assert host.walkthrough.progress.skipped == ()
    host.walkthrough_panel.pause_button.click()
    host.save_note()
    assert host.walkthrough.progress.step == 0
    assert len(host.store.list()) == 1


def test_deleted_practice_note_recovers_without_creating_sample_data(host):
    host.show_getting_started()
    host.note_input.setPlainText("Old clue")
    host.save_note()
    host.store.move_to_trash(host.walkthrough.progress.note_id)
    host.walkthrough_panel.action_button.click()
    assert host.walkthrough.progress.step == 1
    assert "Write another note" in host.walkthrough_panel.description.text()
    assert not host.store.list()
    host.note_input.setPlainText("Replacement")
    host.pin_note()
    assert host.walkthrough.progress.step == 2


def test_cancel_failed_capture_and_restored_pin_do_not_advance(host, monkeypatch):
    host.show_getting_started()
    host.walkthrough_panel.skip_button.click()
    note = Card(None, CardKind.NOTE, "General", "Restored", content="Saved earlier")
    host.store.add(note)
    host.show_pin(note, persist=False)
    assert host.walkthrough.progress.step == 1
    host.walkthrough_panel.skip_button.click()
    host.start_capture()
    host._capture_timer.stop()
    host._capture_cancelled()
    assert host.walkthrough.progress.step == 2
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)
    host.start_capture()
    host._capture_timer.stop()
    host._save_capture(QImage())
    assert host.walkthrough.progress.step == 2


def test_capture_preserves_hidden_preference_and_live_shortcuts(host):
    host.show_getting_started()
    host.walkthrough_panel.skip_button.click()
    host.walkthrough_panel.skip_button.click()
    host.shortcuts["capture_area"] = "Ctrl+Alt+F8"
    host.shortcuts["toggle_panel"] = "Ctrl+Alt+F9"
    host.shortcuts_changed.emit(host.shortcuts)
    assert "Ctrl+Alt+F8" in host.walkthrough_panel.description.text()
    host.settings.setValue("capture/keep_panel_hidden", True)
    capture(host)
    assert not host.isVisible()
    assert host.walkthrough.progress.step == 3
    assert "Ctrl+Alt+F9" in host.walkthrough_panel.description.text()


def test_busy_and_shutdown_actions_do_not_start_or_advance(host):
    host._quitting = True
    host.show_getting_started()
    assert host.walkthrough.progress.paused
    host._quitting = False
    host.show_getting_started()
    host.start_capture()
    host._capture_timer.stop()
    host.show_getting_started()
    assert not host.isVisible()
    host._capture_cancelled()


def test_blocked_first_run_is_not_marked_as_seen(host):
    host.settings.setValue("onboarding/completed", False)
    host._quitting = True
    host._show_first_run_setup()
    assert not host.settings.value("onboarding/completed", False, type=bool)
    host._quitting = False
    host._show_first_run_setup()
    assert not host.walkthrough.progress.paused


def test_modal_and_import_guards_prevent_focus_stealing(host, qt_application):
    host._card_pack_dialog = object()
    host.show_getting_started()
    assert host.walkthrough.progress.paused
    host._card_pack_dialog = None
    modal = QDialog(host)
    modal.setModal(True)
    modal.show()
    qt_application.processEvents()
    host.show_getting_started()
    assert host.walkthrough.progress.paused
    modal.reject()
    modal.deleteLater()


def test_failed_capture_database_write_does_not_complete_step(host, monkeypatch):
    host.show_getting_started()
    host.walkthrough_panel.skip_button.click()
    host.walkthrough_panel.skip_button.click()
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)

    def fail(_):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(host.store, "add", fail)
    capture(host)
    assert host.walkthrough.progress.step == 2
    assert not list(host.captures_dir.glob("*.png"))


def test_quick_panel_success_can_finish_while_main_window_hidden(host):
    host.show_getting_started()
    for _ in range(3):
        host.walkthrough_panel.skip_button.click()
    host.show_quick_panel()
    assert host.walkthrough.progress.step == 4
    assert not host.isVisible()
    assert "1 completed; 3 skipped" in host.walkthrough_panel.description.text()


def test_pinning_storage_error_stays_recoverable(host, monkeypatch):
    host.show_getting_started()
    host.note_input.setPlainText("Saved clue")
    host.save_note()

    def fail(*_):
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(host.store, "update_pinned", fail)
    host.walkthrough_panel.action_button.click()
    assert host.walkthrough.progress.step == 1
    assert "try again" in host.walkthrough_panel.description.text()
    assert host.store.get(host.walkthrough.progress.note_id).content == "Saved clue"
