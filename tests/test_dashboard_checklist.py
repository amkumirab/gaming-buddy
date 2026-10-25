from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.fixture
def panel(qt_application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        window = Dashboard(store, tmp_path / "captures")
        yield window
        window.note_draft_timer.stop()
        window.game_detector.stop()
        for pin in window.pins.values():
            pin.discard_pending_layout()
            pin.close()
            pin.deleteLater()
        window.pins.clear()
        window.tray.hide()
        window._really_quit = True
        window.close()
        window.deleteLater()
        qt_application.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def make_pin(panel):
    card = panel.store.add(Card(None, CardKind.NOTE, "Game", "Preparation",
                                content="# Boss\n\n- [ ] Potion\n- [x] Map\n",
                                tags=("boss",), favorite=True, locked=True))
    panel.show_pin(card)
    return card, panel.pins[card.id]


def toggle(pin, index=0):
    pin.note_view.setTextCursor(QTextCursor(pin.note_view.items[index].block))
    QTest.keyClick(pin.note_view, Qt.Key.Key_Space)


def test_pin_toggle_persists_and_updates_preview_without_replacing_pin(panel):
    card, pin = make_pin(panel)
    before = panel.store.get(card.id)
    toggle(pin)
    saved = panel.store.get(card.id)
    assert saved.content == card.content == "# Boss\n\n- [x] Potion\n- [x] Map\n"
    assert saved.tags == before.tags and saved.favorite and saved.locked and saved.pinned
    assert (saved.x, saved.y, saved.width, saved.height) == (before.x, before.y, before.width, before.height)
    assert pin.checklist_progress.text() == "2 of 2 completed"
    assert panel.pins[card.id] is pin
    assert "Potion" in panel.card_preview.content.toPlainText()
    panel._unpin_card(card)
    panel.show_pin(panel.store.get(card.id))
    assert panel.pins[card.id].checklist_progress.text() == "2 of 2 completed"


def test_failed_save_keeps_checkbox_unchecked_and_reports_failure(panel):
    card, pin = make_pin(panel)
    original = card.content
    panel.store._connection.execute(
        "CREATE TRIGGER reject_check BEFORE UPDATE OF content ON cards "
        "BEGIN SELECT RAISE(ABORT,'failure'); END"
    )
    toggle(pin)
    assert panel.store.get(card.id).content == card.content == pin.note_view.source == original
    assert not pin.note_view.items[0].checked
    assert "Could not save" in pin.checklist_progress.text()


def test_stale_pin_and_shutdown_cannot_overwrite_note(panel):
    card, pin = make_pin(panel)
    original = card.content
    assert panel.store.update_note_content(card.id, expected=original, content="Changed elsewhere")
    toggle(pin)
    assert panel.store.get(card.id).content == "Changed elsewhere"
    assert pin.note_view.source == original
    assert panel.store.update_note_content(card.id, expected="Changed elsewhere", content=original)
    panel._quitting = True
    toggle(pin, 1)
    assert panel.store.get(card.id).content == original


def test_quick_note_checklist_button_updates_the_draft(panel):
    panel.note_input.setPlainText("Potion\nMap")
    panel.note_input.selectAll()
    panel.note_checklist_button.click()
    assert panel.note_input.toPlainText() == "- [ ] Potion\n- [ ] Map"
    assert panel._save_note_draft()
    assert panel.note_draft_store.load().text == "- [ ] Potion\n- [ ] Map"


def test_click_through_disables_checklist_keyboard_changes(panel):
    card, pin = make_pin(panel)
    original = card.content
    pin.set_click_through(True)
    toggle(pin)
    assert panel.store.get(card.id).content == original
    pin.set_click_through(False)
    toggle(pin)
    assert panel.store.get(card.id).content != original


def test_refresh_failure_after_commit_does_not_revert_task(panel, monkeypatch):
    card, pin = make_pin(panel)

    def failed_refresh():
        raise OSError("Refresh unavailable")

    monkeypatch.setattr(panel, "refresh_cards", failed_refresh)
    toggle(pin)
    assert panel.store.get(card.id).content == pin.note_view.source == card.content
    assert pin.note_view.items[0].checked
    assert pin.checklist_progress.text() == "2 of 2 completed"
