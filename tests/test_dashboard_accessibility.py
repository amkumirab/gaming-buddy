from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

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


def _dashboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CardStore, Dashboard]:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    store = CardStore(tmp_path / "cards.sqlite3")
    return store, Dashboard(store, tmp_path / "captures")


def _close_dashboard(store: CardStore, dashboard: Dashboard) -> None:
    dashboard.game_detector.stop()
    dashboard.tray.hide()
    dashboard._really_quit = True
    dashboard.close()
    store.close()


def test_dashboard_groups_workflows_into_accessible_tabs(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, dashboard = _dashboard(tmp_path, monkeypatch)
    try:
        dashboard.show()
        application.processEvents()

        assert [
            dashboard.main_tabs.tabText(index)
            for index in range(dashboard.main_tabs.count())
        ] == ["Capture", "Workspace", "Library"]
        assert dashboard.main_tabs.accessibleName() == "Main navigation"
        dashboard.resize(830, 730)
        dashboard.main_tabs.setCurrentIndex(1)
        application.processEvents()
        assert dashboard.workspace_scroll.verticalScrollBar().maximum() > 0
        assert dashboard.workspace_scroll.horizontalScrollBar().maximum() == 0
        assert dashboard.game_input.accessibleName() == "Current game"
        assert dashboard.note_input.accessibleName() == "Quick note"
        assert dashboard.card_list.accessibleName() == "Saved card library"

        buttons = dashboard.main_tabs.findChildren(QPushButton)
        assert buttons
        assert all(button.accessibleName() for button in buttons)
        assert all(button.toolTip() for button in buttons)
        assert all(not button.icon().isNull() for button in buttons)
    finally:
        _close_dashboard(store, dashboard)


def test_library_uses_clear_empty_states_and_standard_icons(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, dashboard = _dashboard(tmp_path, monkeypatch)
    try:
        assert dashboard.card_list.count() == 0
        assert dashboard.library_empty_label.isHidden() is False
        assert dashboard.library_empty_label.text().startswith("No saved cards yet")

        store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="General",
                title="First clue",
                content="Take the path on the left.",
            )
        )
        dashboard.refresh_cards()

        assert dashboard.library_empty_label.isHidden() is True
        assert dashboard.card_list.count() == 1
        item = dashboard.card_list.item(0)
        assert item.icon().isNull() is False
        assert not any(marker in item.text() for marker in "▣◆●★")

        dashboard.search_cards.setText("does-not-exist")
        application.processEvents()

        assert dashboard.card_list.count() == 0
        assert dashboard.library_empty_label.text() == "No cards match your search or filters."
    finally:
        _close_dashboard(store, dashboard)
