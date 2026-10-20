from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, QSettings, Qt
from PySide6.QtTest import QTest

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.fixture
def library(tmp_path, monkeypatch, qt_application):
    settings_path = str(tmp_path / "settings.ini")

    def settings(*_args):
        return QSettings(settings_path, QSettings.Format.IniFormat)

    preferences = settings()
    preferences.setValue("onboarding/completed", True)
    preferences.setValue("updates/automatic_checks", False)
    preferences.setValue("preview/visible", False)
    preferences.sync()
    monkeypatch.setattr(dashboard_module, "QSettings", settings)
    panels = []
    with CardStore(tmp_path / "cards.sqlite3") as store:
        for day, title in enumerate(("Zebra", "alpha", "Bravo"), start=1):
            store.add(Card(
                None, CardKind.NOTE, "Game", title, content=f"Clue for {title}",
                favorite=day != 2, tags=("puzzle",),
                created_at=f"2026-01-{day:02}T12:00:00+00:00",
            ))

        def create():
            panel = Dashboard(store, tmp_path / "captures")
            panels.append(panel)
            return panel

        yield store, create, preferences
        for panel in panels:
            panel.note_draft_timer.stop()
            panel.game_detector.stop()
            panel.tray.hide()
            panel._really_quit = True
            panel.close()
            panel.deleteLater()
        qt_application.processEvents()


def titles(panel):
    return [panel.card_list.item(row).text().splitlines()[0]
            for row in range(panel.card_list.count())]


def choose_sort(panel, value):
    index = panel.library_sort.findData(value)
    assert index >= 0
    panel.library_sort.setCurrentIndex(index)


@pytest.mark.parametrize(
    ("sort", "expected"),
    [("newest", ["Bravo", "alpha", "Zebra"]),
     ("oldest", ["Zebra", "alpha", "Bravo"]),
     ("title", ["alpha", "Bravo", "Zebra"])],
)
def test_sort_control_reorders_cards_and_persists_across_panel_reopen(library, sort, expected):
    _store, create, preferences = library
    panel = create()
    choose_sort(panel, sort)

    assert titles(panel) == expected
    preferences.sync()
    assert preferences.value("library/sort") == sort
    panel._really_quit = True
    panel.close()
    reopened = create()
    assert reopened.library_sort.currentData() == sort
    assert titles(reopened) == expected


@pytest.mark.parametrize("value", [None, "future-sort", "title; DROP TABLE cards; --", []])
def test_missing_or_invalid_saved_sort_restores_default(library, value):
    store, create, preferences = library
    if value is not None:
        preferences.setValue("library/sort", value)
        preferences.sync()
    panel = create()

    assert panel.library_sort.currentData() == "default"
    assert titles(panel) == [card.title for card in store.list()]


def test_sort_preserves_current_card_and_its_preview(library):
    _store, create, _preferences = library
    panel = create()
    panel.card_list.setCurrentRow(1)
    current_id = panel.card_list.currentItem().data(Qt.ItemDataRole.UserRole)
    preview_title = panel.card_preview.title.text()
    choose_sort(panel, "title")

    assert panel.card_list.currentItem().data(Qt.ItemDataRole.UserRole) == current_id
    assert panel.card_preview.title.text() == preview_title
    assert len(panel.card_list.selectedItems()) == 1


def test_sort_preserves_multi_selection_even_when_current_card_is_not_selected(library):
    _store, create, _preferences = library
    panel = create()
    panel.card_list.clearSelection()
    panel.card_list.item(0).setSelected(True)
    panel.card_list.item(1).setSelected(True)
    panel.card_list.setCurrentItem(
        panel.card_list.item(2), QItemSelectionModel.SelectionFlag.NoUpdate,
    )
    selected = {item.data(Qt.ItemDataRole.UserRole) for item in panel.card_list.selectedItems()}
    current_id = panel.card_list.currentItem().data(Qt.ItemDataRole.UserRole)
    choose_sort(panel, "oldest")

    assert {item.data(Qt.ItemDataRole.UserRole)
            for item in panel.card_list.selectedItems()} == selected
    assert panel.card_list.currentItem().data(Qt.ItemDataRole.UserRole) == current_id
    assert panel.library_selection_label.text() == "2 selected"
    assert panel.card_preview.title.text() == "Select a card"


def test_sort_works_with_search_and_filters_and_clear_filters_keeps_sort(library):
    store, create, _preferences = library
    store.add(Card(None, CardKind.NOTE, "Other", "Other clue", content="Clue"))
    panel = create()
    panel.game_input.setText("Game")
    panel.filter_current.setChecked(True)
    panel.filter_favorites.setChecked(True)
    panel.search_cards.setText("Clue")
    panel._set_library_tag_filter("puzzle")
    choose_sort(panel, "title")

    assert titles(panel) == ["Bravo", "Zebra"]
    assert panel.search_cards.text() == "Clue"
    assert panel.filter_current.isChecked() and panel.filter_favorites.isChecked()
    assert panel._library_tag_filter == "puzzle"
    panel._clear_library_filters()
    assert panel.library_sort.currentData() == "title"
    assert titles(panel) == ["alpha", "Bravo", "Other clue", "Zebra"]


def test_sorting_an_empty_search_keeps_the_empty_state(library):
    _store, create, _preferences = library
    panel = create()
    panel.search_cards.setText("no matching cards")
    choose_sort(panel, "newest")

    assert panel.card_list.count() == 0
    assert not panel.library_empty_label.isHidden()
    assert panel.library_empty_label.text() == "No cards match your search or filters."
    assert panel.card_preview.title.text() == "Select a card"


def test_sort_control_is_labeled_keyboard_accessible_and_fits_compact_panel(
    library, qt_application,
):
    _store, create, _preferences = library
    panel = create()
    panel.main_tabs.setCurrentIndex(2)
    panel.resize(470, 730)
    panel.show()
    panel.activateWindow()
    qt_application.processEvents()
    assert panel.library_sort.accessibleName() == "Sort saved cards"
    assert panel.library_sort.toolTip()
    assert not panel.library_sort.isEditable()
    panel.search_cards.setFocus()
    QTest.keyClick(panel.search_cards, Qt.Key.Key_Tab)
    assert panel.library_sort.hasFocus()
    QTest.keyClick(panel.library_sort, Qt.Key.Key_Down)
    assert panel.library_sort.currentData() == "newest"
    assert titles(panel) == ["Bravo", "alpha", "Zebra"]
    assert panel.width() <= 470
    assert panel.search_cards.width() >= 100
    assert panel.library_sort.width() >= panel.library_sort.sizeHint().width()
