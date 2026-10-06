from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit, QTabWidget

from gaming_buddy.capture_workflow import (
    DEFAULT_CAPTURE_ACTION,
    DEFAULT_CAPTURE_DELAY_SECONDS,
    DEFAULT_CAPTURE_NOTIFICATIONS,
    DEFAULT_KEEP_PANEL_HIDDEN,
    CaptureAction,
)
from gaming_buddy.diagnostics import DiagnosticCheck, DiagnosticReport
from gaming_buddy.hotkeys import DEFAULT_SHORTCUTS
from gaming_buddy.settings_dialog import (
    DEFAULT_FOCUS_OPACITY,
    DEFAULT_PIN_OPACITY,
    SettingsDialog,
    SettingsSnapshot,
)


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _snapshot() -> SettingsSnapshot:
    return SettingsSnapshot(
        launch_at_sign_in=True,
        automatic_update_checks=False,
        auto_switch_profiles=True,
        auto_hide_pins=True,
        click_through_pins=True,
        default_pin_opacity=81,
        focus_opacity=64,
        capture_action=CaptureAction.REVIEW,
        capture_delay_seconds=3,
        capture_keep_panel_hidden=False,
        capture_notifications=False,
        shortcuts=DEFAULT_SHORTCUTS.copy(),
    )


def test_missing_capture_monitor_is_preserved_until_user_changes_it(application, tmp_path):
    snapshot = replace(_snapshot(), full_screen_monitor="screen:Disconnected")
    dialog = SettingsDialog(
        snapshot, version="0.1.0", storage_path=tmp_path, startup_supported=True,
    )
    try:
        assert dialog.values().full_screen_monitor == "screen:Disconnected"
        assert "not connected" in dialog.full_screen_monitor.currentText()
        dialog.full_screen_monitor.setCurrentIndex(dialog.full_screen_monitor.findData("pointer"))
        assert dialog.values().full_screen_monitor == "pointer"
        dialog.restore_defaults()
        assert dialog.values().full_screen_monitor == "primary"
    finally:
        dialog.close()


def test_settings_dialog_returns_all_selected_values(
    application: QApplication, tmp_path: Path
) -> None:
    dialog = SettingsDialog(
        _snapshot(),
        version="1.2.3",
        storage_path=tmp_path,
        startup_supported=True,
    )

    assert dialog.values() == _snapshot()
    assert dialog.default_pin_opacity[1].orientation() == Qt.Orientation.Horizontal
    text = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Version 1.2.3" in text
    path = next(field for field in dialog.findChildren(QLineEdit) if field.isReadOnly())
    assert path.text() == str(tmp_path)


def test_restore_defaults_updates_controls_without_accepting(
    application: QApplication, tmp_path: Path
) -> None:
    dialog = SettingsDialog(
        _snapshot(),
        version="1.2.3",
        storage_path=tmp_path,
        startup_supported=True,
    )
    dialog.restore_defaults()
    values = dialog.values()

    assert values.launch_at_sign_in is False
    assert values.automatic_update_checks is True
    assert values.auto_switch_profiles is False
    assert values.auto_hide_pins is False
    assert values.click_through_pins is False
    assert values.default_pin_opacity == DEFAULT_PIN_OPACITY
    assert values.focus_opacity == DEFAULT_FOCUS_OPACITY
    assert values.capture_action is DEFAULT_CAPTURE_ACTION
    assert values.capture_delay_seconds == DEFAULT_CAPTURE_DELAY_SECONDS
    assert values.capture_keep_panel_hidden is DEFAULT_KEEP_PANEL_HIDDEN
    assert values.capture_notifications is DEFAULT_CAPTURE_NOTIFICATIONS
    assert values.shortcuts == DEFAULT_SHORTCUTS
    assert dialog.result() == 0


def test_startup_control_is_disabled_when_unavailable(
    application: QApplication, tmp_path: Path
) -> None:
    dialog = SettingsDialog(
        _snapshot(),
        version="1.2.3",
        storage_path=tmp_path,
        startup_supported=False,
    )
    startup = next(
        checkbox
        for checkbox in dialog.findChildren(QCheckBox)
        if checkbox.text().startswith("Launch Gaming Buddy")
    )

    assert startup.isEnabled() is False


def test_duplicate_shortcuts_are_rejected_by_values(
    application: QApplication, tmp_path: Path
) -> None:
    dialog = SettingsDialog(
        _snapshot(),
        version="1.2.3",
        storage_path=tmp_path,
        startup_supported=True,
    )
    duplicate = QKeySequence(DEFAULT_SHORTCUTS["toggle_panel"])
    dialog._shortcut_editors["capture_area"].setKeySequence(duplicate)

    with pytest.raises(ValueError, match="already assigned"):
        dialog.values()


def test_troubleshooting_does_not_save_settings_or_accept_the_dialog(
    application: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    copies: list[str] = []

    class Clipboard:
        def setText(self, text: str) -> None:
            copies.append(text)

    monkeypatch.setattr(QApplication, "clipboard", lambda: Clipboard())

    def provider() -> DiagnosticReport:
        calls.append(1)
        return DiagnosticReport(
            (), (DiagnosticCheck("Shortcuts", "Paused in Settings", "Close Settings."),),
        )

    values = _snapshot()
    dialog = SettingsDialog(
        values, version="1.2.3", storage_path=tmp_path,
        startup_supported=True, diagnostics_provider=provider,
    )
    try:
        tabs = dialog.findChild(QTabWidget)
        assert tabs is not None
        tabs.setCurrentWidget(dialog.troubleshooting)
        dialog.show()
        application.processEvents()
        dialog.troubleshooting.run_button.setFocus()
        QTest.keyClick(dialog.troubleshooting.run_button, Qt.Key.Key_Space)
        assert calls == [1]
        QTest.keyClick(dialog.troubleshooting.run_button, Qt.Key.Key_Return)
        assert calls == [1, 1]
        QTest.keyClick(dialog.troubleshooting.run_button, Qt.Key.Key_Tab)
        assert dialog.focusWidget() is dialog.troubleshooting.copy_button
        QTest.keyClick(dialog.troubleshooting.copy_button, Qt.Key.Key_Return)
        assert copies == [dialog.troubleshooting.report_view.toPlainText()]
        assert dialog.isVisible()
        assert dialog.result() == 0
        assert dialog.values() == values
    finally:
        dialog.close()
