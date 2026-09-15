from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QAbstractItemView, QApplication

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_dashboard_preserves_multi_selection_during_bulk_favorite(
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
        first = store.add(Card(None, CardKind.NOTE, "Game", "First"))
        second = store.add(Card(None, CardKind.NOTE, "Game", "Second"))
        dashboard = Dashboard(store, captures)
        try:
            assert (
                dashboard.card_list.selectionMode()
                == QAbstractItemView.SelectionMode.ExtendedSelection
            )
            dashboard.card_list.item(0).setSelected(True)
            dashboard.card_list.item(1).setSelected(True)
            dashboard._update_selection_summary()

            assert dashboard.library_selection_label.text() == "2 selected"
            assert dashboard.bulk_actions_button.isHidden() is False

            dashboard._bulk_set_favorite(True)

            assert store.get(first.id).favorite is True
            assert store.get(second.id).favorite is True
            assert len(dashboard.card_list.selectedItems()) == 2
        finally:
            dashboard.game_detector.stop()
            dashboard.tray.hide()
            dashboard._really_quit = True
            dashboard.close()
