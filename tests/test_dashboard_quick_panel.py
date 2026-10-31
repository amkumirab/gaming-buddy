import sqlite3

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.fixture
def dashboard(qt_application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        host = Dashboard(store, tmp_path / "captures")
        for timer in host._startup_timers:
            timer.stop()
        yield host
        host.note_draft_timer.stop()
        host._capture_timer.stop()
        host.game_detector.stop()
        for pin in host.pins.values():
            pin.discard_pending_layout()
            pin.close()
            pin.deleteLater()
        host.tray.hide()
        host._really_quit = True
        host.close()
        host.deleteLater()
        qt_application.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def open_quick(host):
    host.quick_panel.show()
    return host.quick_panel.panel


def test_switch_surfaces_reuses_one_window_and_keeps_existing_draft(dashboard):
    dashboard.note_input.setPlainText("Draft from the full panel")
    dashboard.show()
    quick = open_quick(dashboard)
    assert quick.parentWidget() is dashboard
    assert quick.isVisible() and not dashboard.isVisible()
    assert quick.note_editor.toPlainText() == "Draft from the full panel"
    quick.note_button.click()
    quick.note_editor.setPlainText("Changed\n\nfrom compact")
    quick.full_panel_button.click()
    assert dashboard.isVisible() and not quick.isVisible()
    assert dashboard.note_input.toPlainText() == "Changed\n\nfrom compact"
    assert open_quick(dashboard) is quick
    dashboard.show_panel()
    assert not quick.isVisible()


@pytest.mark.parametrize("pin", [False, True])
def test_save_uses_shared_store_and_clears_both_editors(dashboard, pin):
    dashboard.game_input.setText("Puzzle game")
    quick = open_quick(dashboard)
    quick.note_button.click()
    quick.note_editor.setPlainText("Door code\n\n1234")
    (quick.pin_button if pin else quick.save_button).click()
    cards = dashboard.store.list()
    assert len(cards) == 1
    assert cards[0].content == "Door code\n\n1234"
    assert cards[0].game == "Puzzle game"
    assert cards[0].pinned is pin
    assert dashboard.note_input.toPlainText() == quick.note_editor.toPlainText() == ""
    assert dashboard.note_draft_store.load() is None


def test_failed_save_keeps_shared_draft_and_reports_error(dashboard, monkeypatch):
    quick = open_quick(dashboard)
    quick.note_button.click()
    quick.note_editor.setPlainText("Unsaved clue")
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)

    def unavailable(_card):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(dashboard.store, "add", unavailable)
    quick.save_button.click()
    assert not dashboard.store.list()
    assert quick.note_editor.toPlainText() == dashboard.note_input.toPlainText() == "Unsaved clue"
    assert "not saved" in quick.status.text().lower()
    assert dashboard._save_note_draft()
    assert dashboard.note_draft_store.load().text == "Unsaved clue"


def test_full_panel_save_clears_hidden_quick_editor(dashboard):
    quick = open_quick(dashboard)
    quick.note_editor.setPlainText("Shared draft")
    dashboard.show_panel()
    dashboard.save_note()
    assert quick.note_editor.toPlainText() == ""
    assert len(dashboard.store.list()) == 1


def test_profile_label_and_finder_follow_current_game(dashboard):
    quick = open_quick(dashboard)
    dashboard.game_input.setText("RPG")
    assert quick.game_label.toolTip() == "RPG"
    quick.find_button.click()
    assert not quick.isVisible()
    assert dashboard._quick_finder is not None and dashboard._quick_finder.isVisible()
    dashboard._quick_finder.reject()


def test_capture_cancel_restores_quick_panel_not_dashboard(dashboard):
    quick = open_quick(dashboard)
    quick.capture_button.click()
    assert dashboard._capture_in_progress
    assert not quick.isVisible() and not dashboard.isVisible()
    dashboard.quick_panel.show()
    assert not quick.isVisible()
    dashboard._capture_timer.stop()
    dashboard._capture_cancelled()
    assert quick.isVisible() and not dashboard.isVisible()


@pytest.mark.parametrize("keep_hidden", [False, True])
def test_capture_success_respects_quick_origin_and_hidden_setting(dashboard, keep_hidden):
    dashboard.settings.setValue("capture/keep_panel_hidden", keep_hidden)
    dashboard.settings.setValue("capture/notifications", False)
    dashboard.settings.setValue("capture/action", "save_only")
    quick = open_quick(dashboard)
    dashboard.start_capture()
    dashboard._capture_timer.stop()
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    dashboard._save_capture(image)
    assert len(dashboard.store.list()) == 1
    assert quick.isVisible() is not keep_hidden
    assert not dashboard.isVisible()


def test_full_monitor_capture_hides_quick_panel_before_grab(dashboard, monkeypatch):
    quick = open_quick(dashboard)
    monkeypatch.setattr(dashboard_module, "select_monitor", lambda *_: object())

    def grab(_screen):
        assert not quick.isVisible()
        image = QImage(16, 16, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.blue)
        return image

    monkeypatch.setattr(dashboard_module, "grab_monitor", grab)
    dashboard.settings.setValue("capture/notifications", False)
    dashboard.start_full_screen_capture()
    assert not quick.isVisible() and not dashboard.isVisible()
    assert len(dashboard.store.list()) == 1


def test_modal_capture_and_shutdown_admission_guards(dashboard, qt_application):
    quick = open_quick(dashboard)
    quick.note_editor.setPlainText("Keep this draft")
    quick.hide()
    modal = QDialog()
    modal.setModal(True)
    modal.show()
    qt_application.processEvents()
    try:
        dashboard.quick_panel.show()
        assert not quick.isVisible()
    finally:
        modal.close()
        modal.deleteLater()
    dashboard._quitting = True
    dashboard.shutdown_started.emit()
    dashboard.quick_panel.show()
    quick.save_requested.emit(False)
    assert not dashboard.store.list()
    assert not quick.isVisible()
    dashboard._quitting = False
    dashboard.shutdown_cancelled.emit()
    dashboard.quick_panel.show()
    assert quick.isVisible() and quick.note_editor.toPlainText() == "Keep this draft"


def test_hidden_panel_position_is_remembered_and_offscreen_position_is_recovered(dashboard):
    quick = open_quick(dashboard)
    quick.move(120, 120)
    quick.hide()
    assert dashboard.settings.value("quick_panel/position") == quick.pos()
    dashboard.settings.setValue("quick_panel/position", QPoint(100000, -100000))
    dashboard.quick_panel.show()
    assert any(screen.availableGeometry().intersects(quick.frameGeometry())
               for screen in dashboard_module.QGuiApplication.screens())


def test_normal_note_enter_does_not_accidentally_save(dashboard):
    quick = open_quick(dashboard)
    quick.note_button.click()
    quick.note_editor.setPlainText("First")
    quick.note_editor.moveCursor(quick.note_editor.textCursor().MoveOperation.End)
    QTest.keyClick(quick.note_editor, Qt.Key.Key_Return)
    assert quick.note_editor.toPlainText() == "First\n"
    assert not dashboard.store.list()


def test_capture_failure_recovers_full_panel_and_clears_quick_origin(dashboard, monkeypatch):
    quick = open_quick(dashboard)

    def failed_capture():
        raise RuntimeError("Capture unavailable")

    monkeypatch.setattr(dashboard_module, "begin_capture", failed_capture)
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)
    dashboard.start_capture()
    dashboard._capture_timer.stop()
    dashboard._open_capture_overlay()
    assert dashboard.isVisible() and not quick.isVisible()
    assert not dashboard._capture_in_progress
    assert not dashboard.quick_panel.capture_finished(restore=True)


def test_entering_focus_mode_dismisses_quick_panel_without_losing_draft(dashboard):
    card = dashboard.store.add(Card(None, CardKind.NOTE, "General", "Map", content="North"))
    dashboard.show_pin(card)
    quick = open_quick(dashboard)
    quick.note_editor.setPlainText("Draft for later")
    assert dashboard.note_draft_timer.isActive()
    dashboard.set_focus_mode(True)
    assert dashboard.focus_mode.active
    assert not quick.isVisible()
    assert dashboard.note_input.toPlainText() == "Draft for later"
    dashboard.set_focus_mode(False)


def test_import_guard_blocks_opening_and_saving_queued_actions(dashboard):
    quick = open_quick(dashboard)
    quick.note_editor.setPlainText("Keep during import")
    quick.hide()
    dashboard._card_pack_dialog = object()
    try:
        dashboard.show_quick_panel()
        quick.save_requested.emit(False)
        assert not quick.isVisible()
        assert not dashboard.store.list()
    finally:
        dashboard._card_pack_dialog = None
    dashboard.show_quick_panel()
    assert quick.note_editor.toPlainText() == "Keep during import"
