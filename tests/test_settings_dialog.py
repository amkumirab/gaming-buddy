from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QLineEdit

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
        shortcuts=DEFAULT_SHORTCUTS.copy(),
    )


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
