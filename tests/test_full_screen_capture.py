import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QPoint, QRect, QSettings
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

import gaming_buddy.capture as capture_module
import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.capture import grab_monitor, select_monitor
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.hotkeys import DEFAULT_SHORTCUTS, complete_shortcuts
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore
from gaming_buddy.workspace_backup import create_workspace_backup


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


class Monitor:
    def __init__(self, name, geometry, image):
        self._name, self._geometry, self.image = name, geometry, image

    def name(self):
        return self._name

    def geometry(self):
        return self._geometry

    def grabWindow(self, window):
        assert window == 0
        return QPixmap.fromImage(self.image)


def test_monitor_selection_uses_primary_pointer_and_saved_name(application, monkeypatch):
    primary = Monitor("Main", QRect(0, 0, 100, 50), QImage())
    secondary = Monitor("Second", QRect(-100, 0, 100, 50), QImage())
    monkeypatch.setattr(capture_module.QGuiApplication, "screens", lambda: [primary, secondary])
    monkeypatch.setattr(capture_module.QGuiApplication, "primaryScreen", lambda: primary)
    monkeypatch.setattr(capture_module.QCursor, "pos", lambda: QPoint(-30, 10))
    assert select_monitor("primary") is primary
    assert select_monitor("pointer") is secondary
    assert select_monitor("screen:Second") is secondary
    with pytest.raises(RuntimeError, match="not connected"):
        select_monitor("screen:Disconnected")


def test_no_displays_produces_an_actionable_error(application, monkeypatch):
    monkeypatch.setattr(capture_module.QGuiApplication, "screens", list)
    with pytest.raises(RuntimeError, match="No display"):
        select_monitor("primary")


def test_invalid_monitor_setting_does_not_capture_another_display(application, monkeypatch):
    monitor = Monitor("Main", QRect(0, 0, 100, 50), QImage())
    monkeypatch.setattr(capture_module.QGuiApplication, "screens", lambda: [monitor])
    monkeypatch.setattr(capture_module.QGuiApplication, "primaryScreen", lambda: monitor)
    with pytest.raises(RuntimeError, match="Settings > Capture"):
        select_monitor("invalid-preference")


def test_full_monitor_capture_preserves_native_pixels(application, tmp_path: Path):
    image = QImage(200, 100, QImage.Format.Format_RGBA8888)
    image.fill(0xFF123456)
    image.setDevicePixelRatio(2)
    monitor = Monitor("HiDPI", QRect(-100, 0, 100, 50), image)
    result = grab_monitor(monitor)
    assert result.size() == image.size()
    assert result.devicePixelRatio() == 1
    destination = tmp_path / "native.png"
    assert result.save(str(destination), "PNG")
    assert QImage(str(destination)).pixelColor(150, 75) == image.pixelColor(150, 75)


def test_empty_capture_is_not_saved(application):
    with pytest.raises(RuntimeError, match="could not be captured"):
        grab_monitor(Monitor("Empty", QRect(0, 0, 100, 50), QImage()))


def test_new_shortcut_preserves_existing_bindings_when_default_is_taken():
    saved = {key: value for key, value in DEFAULT_SHORTCUTS.items() if key != "capture_screen"}
    saved["capture_area"] = "Ctrl+Shift+D"
    upgraded = complete_shortcuts(saved)
    assert upgraded["capture_area"] == "Ctrl+Shift+D"
    assert upgraded["capture_screen"] != "Ctrl+Shift+D"
    assert all(upgraded[key] == value for key, value in saved.items())


@pytest.fixture
def dashboard(application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    settings.setValue("capture/action", "review")
    settings.setValue("capture/delay_seconds", 5)
    settings.setValue("capture/keep_panel_hidden", False)
    settings.setValue("capture/notifications", False)
    settings.setValue("shortcuts/capture_area", "Ctrl+Shift+D")
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    store = CardStore(tmp_path / "cards.sqlite3")
    panel = Dashboard(store, tmp_path / "captures")
    application.processEvents()
    try:
        yield panel
    finally:
        panel.note_draft_timer.stop()
        panel.game_detector.stop()
        panel.tray.hide()
        panel._really_quit = True
        panel.close()
        store.close()


def test_instant_capture_saves_without_selection_review_pinning_or_panel_focus(
    dashboard, monkeypatch, application,
):
    image = QImage(400, 200, QImage.Format.Format_RGBA8888)
    image.fill(0xFF123456)
    monkeypatch.setattr(dashboard_module, "select_monitor", lambda _preference: object())
    def capture(_screen):
        assert dashboard.isHidden()
        # A profile change during the screen grab must not change the captured card's game.
        dashboard.game_input.setText("Other game")
        return image
    monkeypatch.setattr(dashboard_module, "grab_monitor", capture)
    monkeypatch.setattr(dashboard, "_review_capture", lambda _image: pytest.fail("Review opened"))
    dashboard.game_input.setText("Current game")
    dashboard.show()
    application.processEvents()
    dashboard.start_full_screen_capture()
    cards = dashboard.store.list()
    assert len(cards) == 1
    assert cards[0].game == "Current game"
    assert not cards[0].pinned
    assert QImage(cards[0].image_path).size() == image.size()
    assert not dashboard.pins
    assert dashboard.isHidden()
    assert not dashboard._capture_in_progress
    assert dashboard.shortcuts["capture_area"] == "Ctrl+Shift+D"
    assert dashboard.shortcuts["capture_screen"] != "Ctrl+Shift+D"


def test_full_capture_does_not_interrupt_an_area_capture(dashboard, monkeypatch):
    dashboard._capture_in_progress = True
    monkeypatch.setattr(dashboard_module, "select_monitor", lambda *_args: pytest.fail("New capture"))
    dashboard.start_full_screen_capture()
    assert dashboard.store.list() == []
    assert dashboard._capture_in_progress


def test_missing_monitor_records_failure_and_allows_retry(dashboard, monkeypatch):
    def missing(_preference):
        raise RuntimeError("The selected monitor is not connected.")
    monkeypatch.setattr(dashboard_module, "select_monitor", missing)
    warnings = []
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_args: warnings.append(1))
    dashboard.start_full_screen_capture()
    assert warnings == [1]
    assert not dashboard._capture_in_progress
    assert dashboard.store.list() == []
    assert len(dashboard.diagnostic_history.snapshot()) == 1


@pytest.mark.parametrize("failed", [False, True])
def test_pins_are_hidden_during_grab_and_restored_even_on_failure(
    dashboard, monkeypatch, application, failed,
):
    card = dashboard.store.add(Card(None, CardKind.NOTE, "General", "Clue", content="Safe code"))
    dashboard.show_pin(card)
    pin = dashboard.pins[card.id]
    application.processEvents()
    assert pin.isVisible()
    monkeypatch.setattr(dashboard_module, "select_monitor", lambda _preference: object())
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_args: None)
    def capture(_screen):
        assert not pin.isVisible()
        if failed:
            raise RuntimeError("Monitor capture failed")
        image = QImage(200, 100, QImage.Format.Format_RGBA8888)
        image.fill(0xFF123456)
        return image
    monkeypatch.setattr(dashboard_module, "grab_monitor", capture)
    dashboard.start_full_screen_capture()
    assert pin.isVisible()
    assert dashboard.store.get(card.id).pinned
    assert not dashboard._capture_in_progress


def test_failed_database_write_does_not_leave_an_orphan_screenshot(dashboard, monkeypatch):
    monkeypatch.setattr(dashboard_module, "select_monitor", lambda _preference: object())
    image = QImage(200, 100, QImage.Format.Format_RGBA8888)
    image.fill(0xFF123456)
    monkeypatch.setattr(dashboard_module, "grab_monitor", lambda _screen: image)
    def unavailable(_card):
        raise sqlite3.OperationalError("Database unavailable")
    monkeypatch.setattr(dashboard.store, "add", unavailable)
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_args: None)
    dashboard.start_full_screen_capture()
    assert list(dashboard.captures_dir.iterdir()) == []
    assert not dashboard._capture_in_progress


def test_backup_keeps_shortcut_but_does_not_copy_a_device_specific_monitor(dashboard, tmp_path):
    dashboard.settings.setValue("shortcuts/capture_screen", "Ctrl+Alt+D")
    dashboard.settings.setValue("capture/full_screen_monitor", "screen:Private-device")
    backup = tmp_path / "workspace.zip"
    create_workspace_backup(backup, dashboard.store, dashboard.settings)
    with ZipFile(backup) as archive:
        settings = json.loads(archive.read("settings.json"))
    assert settings["shortcuts/capture_screen"] == "Ctrl+Alt+D"
    assert "capture/full_screen_monitor" not in settings


def test_capture_cleanup_failure_reports_saved_file_and_releases_capture_lock(dashboard, monkeypatch):
    image = QImage(200, 100, QImage.Format.Format_RGBA8888)
    image.fill(0xFF123456)
    monkeypatch.setattr(dashboard_module, "select_monitor", lambda _preference: object())
    monkeypatch.setattr(dashboard_module, "grab_monitor", lambda _screen: image)

    def unavailable(_card):
        raise sqlite3.OperationalError("Database unavailable")

    def denied(_path, **_kwargs):
        raise PermissionError("File is locked")

    monkeypatch.setattr(dashboard.store, "add", unavailable)
    monkeypatch.setattr(Path, "unlink", denied)
    warnings = []
    monkeypatch.setattr(
        dashboard_module.QMessageBox, "warning", lambda _parent, _title, message: warnings.append(message)
    )
    dashboard.start_full_screen_capture()
    assert not dashboard._capture_in_progress
    assert dashboard.store.list() == []
    assert len(list(dashboard.captures_dir.iterdir())) == 1
    assert "could not be removed" in warnings[0]
