from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from gaming_buddy.hotkeys import DEFAULT_SHORTCUTS
from gaming_buddy.onboarding import OnboardingDialog


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_onboarding_shows_current_shortcuts_and_display_guidance(
    application: QApplication,
) -> None:
    dialog = OnboardingDialog(DEFAULT_SHORTCUTS, False)
    text = " ".join(label.text() for label in dialog.findChildren(QLabel))

    assert DEFAULT_SHORTCUTS["capture_area"] in text
    assert DEFAULT_SHORTCUTS["toggle_panel"] in text
    assert DEFAULT_SHORTCUTS["quick_finder"] in text
    assert "Borderless Windowed" in text
    assert "Ctrl+V" in text
    assert "extract searchable text" in text
    assert dialog.launch_at_sign_in is False

    dialog.launch_checkbox.setChecked(True)
    assert dialog.launch_at_sign_in is True
