from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from gaming_buddy.preset_dialog import PresetAction, WorkspacePresetDialog
from gaming_buddy.workspace_presets import WorkspacePresetSummary


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_workspace_layout_dialog_handles_empty_list(application: QApplication) -> None:
    dialog = WorkspacePresetDialog("Control", [])

    assert dialog.selected_preset_id is None
    assert dialog.apply_button.isEnabled() is False
    assert dialog.rename_button.isEnabled() is False
    assert dialog.delete_button.isEnabled() is False


def test_workspace_layout_dialog_exposes_selected_action(application: QApplication) -> None:
    summary = WorkspacePresetSummary(7, "Control", "Puzzle", 3, True, "now", "now")
    dialog = WorkspacePresetDialog("Control", [summary])

    assert dialog.selected_preset_id == 7
    assert "Puzzle" in dialog.list.item(0).text()
    assert "3 pins" in dialog.list.item(0).text()
    dialog._choose(PresetAction.APPLY)
    assert dialog.action is PresetAction.APPLY
