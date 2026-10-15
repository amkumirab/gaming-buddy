from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.capture_workflow import (
    CaptureAction,
    capture_start_delay_ms,
    normalize_capture_action,
    normalize_capture_delay,
)
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.image_import import load_clipboard_image
from gaming_buddy.storage import CardStore


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _image() -> QImage:
    image = QImage(640, 360, QImage.Format.Format_RGBA8888)
    image.fill(QColor("#6750a4"))
    return image


def test_capture_preferences_reject_unknown_values() -> None:
    assert normalize_capture_action("save_only") is CaptureAction.SAVE_ONLY
    assert normalize_capture_action("unknown") is CaptureAction.SAVE_AND_PIN
    assert normalize_capture_delay("3") == 3
    assert normalize_capture_delay(9) == 0
    assert capture_start_delay_ms(0) == 180
    assert capture_start_delay_ms(5) == 5000


@pytest.mark.parametrize(
    ("action", "expected_pinned"),
    [
        (CaptureAction.SAVE_AND_PIN, True),
        (CaptureAction.SAVE_ONLY, False),
        (CaptureAction.REVIEW, False),
    ],
)
def test_capture_action_saves_at_full_resolution_and_controls_pinning(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: CaptureAction,
    expected_pinned: bool,
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("capture/action", action.value)
    settings.setValue("capture/keep_panel_hidden", True)
    settings.setValue("capture/notifications", True)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    notifications: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QSystemTrayIcon,
        "showMessage",
        lambda _tray, title, message, *_args: notifications.append((title, message)),
    )
    if action is CaptureAction.REVIEW:
        monkeypatch.setattr(Dashboard, "_review_capture", lambda _dashboard, _image: False)
    captures = tmp_path / "captures"

    with CardStore(tmp_path / "cards.sqlite3") as store:
        dashboard = Dashboard(store, captures)
        try:
            dashboard._capture_in_progress = True
            dashboard._save_capture(_image())

            cards = store.list()
            assert len(cards) == 1
            assert cards[0].pinned is expected_pinned
            saved = QImage(cards[0].image_path)
            assert (saved.width(), saved.height()) == (640, 360)
            assert dashboard.isHidden()
            assert dashboard._capture_in_progress is False
            assert notifications[-1][0] == "Screenshot captured"
            assert "640 × 360 px" in notifications[-1][1]
        finally:
            dashboard.game_detector.stop()
            dashboard.tray.hide()
            dashboard._really_quit = True
            dashboard.close()


def test_cancelled_capture_restores_only_a_previously_visible_panel(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    captures = tmp_path / "captures"
    captures.mkdir()

    with CardStore(tmp_path / "cards.sqlite3") as store:
        dashboard = Dashboard(store, captures)
        try:
            dashboard._capture_panel_was_visible = False
            dashboard._capture_cancelled()
            assert dashboard.isHidden()

            dashboard._capture_panel_was_visible = True
            dashboard._capture_cancelled()
            assert dashboard.isVisible()
        finally:
            dashboard.game_detector.stop()
            dashboard.tray.hide()
            dashboard._really_quit = True
            dashboard.close()


def test_start_capture_uses_saved_delay_and_blocks_a_second_request(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("capture/delay_seconds", 3)
    settings.setValue("capture/notifications", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    captures = tmp_path / "captures"
    captures.mkdir()

    with CardStore(tmp_path / "cards.sqlite3") as store:
        dashboard = Dashboard(store, captures)
        try:
            dashboard.show()
            application.processEvents()
            scheduled: list[int] = []
            monkeypatch.setattr(
                dashboard._capture_timer,
                "start",
                lambda milliseconds: scheduled.append(milliseconds),
            )

            dashboard.start_capture()
            dashboard.start_capture()

            assert scheduled == [3000]
            assert dashboard._capture_in_progress is True
            assert dashboard.isHidden()
            dashboard._capture_cancelled()
            assert dashboard.isVisible()
        finally:
            dashboard.game_detector.stop()
            dashboard.tray.hide()
            dashboard._really_quit = True
            dashboard.close()


def test_image_import_removes_saved_file_when_database_write_fails(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    monkeypatch.setattr(Dashboard, "_choose_image_import_action", lambda *_args: False)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        dashboard_module.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    captures = tmp_path / "captures"
    captures.mkdir()

    with CardStore(tmp_path / "cards.sqlite3") as store:
        dashboard = Dashboard(store, captures)
        try:
            def fail_to_add(_card: object) -> None:
                raise sqlite3.OperationalError("database is unavailable")

            monkeypatch.setattr(store, "add", fail_to_add)

            dashboard._import_images([load_clipboard_image(_image())])

            assert list(captures.iterdir()) == []
            assert warnings
            assert warnings[-1][0] == "Import incomplete"
            assert "Could not add the image to the library" in warnings[-1][1]
        finally:
            dashboard.game_detector.stop()
            dashboard.tray.hide()
            dashboard._really_quit = True
            dashboard.close()
