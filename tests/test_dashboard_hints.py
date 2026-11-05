import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.hint_cards import HintContent
from gaming_buddy.hint_editor import HintEditor
from gaming_buddy.models import Card, CardKind
from gaming_buddy.quick_finder import find_cards
from gaming_buddy.storage import CardStore


@pytest.fixture
def panel(qt_application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        window = Dashboard(store, tmp_path / "captures")
        for timer in window._startup_timers:
            timer.stop()
        window.game_detector.stop()
        yield window
        window._quitting = True
        window.note_draft_timer.stop()
        for pin in window.pins.values():
            pin.discard_pending_layout()
            pin.close()
            pin.deleteLater()
        window.pins.clear()
        window.tray.hide()
        window._really_quit = True
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def guide(panel, progress=0):
    card = panel.store.add(Card(None, CardKind.NOTE, "Game", "Gate guide", height=360,
                                hints=HintContent(("SUBTLE", "GUIDANCE", "SECRET-0451"), progress)))
    panel.show_pin(card)
    return card, panel.pins[card.id]


def test_pin_and_preview_share_progress_and_copy_only_revealed_text(panel):
    card, pin = guide(panel)
    preview = panel.card_preview
    assert preview.card.id == card.id and preview.kind.text() == "HINT"
    assert not preview.copy_button.isEnabled()
    assert not pin.note_view
    assert not find_cards(panel.store.list(), "SECRET-0451")
    QApplication.clipboard().setText("Keep clipboard")
    panel._copy_card(card)
    assert QApplication.clipboard().text() == "Keep clipboard"
    pin.hint_view.reveal_button.click()
    assert panel.store.get(card.id).hints.revealed == 1
    assert preview.hint_view.hints.revealed == 1 and preview.copy_button.isEnabled()
    preview.copy_button.click()
    copied = QApplication.clipboard().text()
    assert "SUBTLE" in copied and "GUIDANCE" not in copied and "SECRET-0451" not in copied
    preview.hint_view.reset_button.click()
    assert pin.hint_view.hints.revealed == 0
    assert "SUBTLE" not in pin.hint_view.content.toPlainText()
    assert not preview.copy_button.isEnabled()
    # A detached snapshot of older progress cannot copy stages hidden by a reset.
    card.hints = card.hints.with_progress(3)
    panel._copy_card(card)
    assert QApplication.clipboard().text() == copied


def test_click_through_failed_save_stale_card_and_shutdown_cannot_reveal(panel):
    card, pin = guide(panel)
    pin.set_click_through(True)
    pin.hint_view.reveal_button.click()
    assert panel.store.get(card.id).hints.revealed == 0
    pin.set_click_through(False)
    panel.store._connection.execute(
        "CREATE TRIGGER reject_hint BEFORE UPDATE ON card_hints "
        "BEGIN SELECT RAISE(ABORT, 'controlled failure'); END"
    )
    pin.hint_view.reveal_button.click()
    assert pin.hint_view.hints.revealed == 0
    assert "SUBTLE" not in pin.hint_view.content.toPlainText()
    panel.store._connection.execute("DROP TRIGGER reject_hint")
    panel.store._connection.commit()
    changed = HintContent(("Different", "More", "NEW-SECRET"))
    panel.store.update_hint_details(card.id, title=card.title, game=card.game, tags=(), hints=changed)
    pin.hint_view.reveal_button.click()
    assert panel.store.get(card.id).hints == changed
    panel._quitting = True
    assert panel._save_hint_progress(card, changed, 1) is None


def test_new_hint_editor_preserves_draft_and_retries_failed_save(panel, monkeypatch):
    panel.note_input.setPlainText("Unfinished quick note\n\nKeep this")
    assert panel._save_note_draft()
    calls = []

    def edit(dialog):
        if calls:
            assert dialog.steps[0].toPlainText() == "First\n\n  clue\n"
            panel.store._connection.execute("DROP TRIGGER reject_hint_insert")
            panel.store._connection.commit()
        else:
            dialog.title_input.setText("Route")
            for field, text in zip(dialog.steps, ("First\n\n  clue\n", "Second", "Final"), strict=True):
                field.setPlainText(text)
        calls.append(dialog)
        return 1

    panel.store._connection.execute(
        "CREATE TRIGGER reject_hint_insert BEFORE INSERT ON card_hints "
        "BEGIN SELECT RAISE(ABORT, 'controlled failure'); END"
    )
    monkeypatch.setattr(HintEditor, "exec", edit)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_: None)
    panel.new_hint_button.click()
    assert len(calls) == 2 and calls[0] is calls[1]
    assert panel.store.list()[0].hints.steps[0] == "First\n\n  clue\n"
    assert panel.store.list()[0].hints.revealed == 0
    assert panel.note_input.toPlainText() == panel.note_draft_store.load().text


def test_edit_warning_can_cancel_and_changed_stages_reset_progress(panel, monkeypatch):
    card, pin = guide(panel, 2)
    calls = []

    def edit(dialog):
        calls.append(dialog)
        dialog.steps[2].setPlainText("NEW-SECRET")
        return 1

    monkeypatch.setattr(HintEditor, "exec", edit)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    panel._edit_card(card)
    assert calls == [] and panel.store.get(card.id).hints.revealed == 2
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    panel._edit_card(card)
    saved = panel.store.get(card.id)
    assert len(calls) == 1 and saved.hints.revealed == 0
    assert saved.hints.steps[2] == "NEW-SECRET"
    replacement = panel.pins[card.id]
    assert replacement is not pin and "NEW-SECRET" not in replacement.hint_view.content.toPlainText()


def test_pin_background_stays_dark_in_the_reading_area(panel):
    _, pin = guide(panel)
    image = pin.grab().toImage()
    scale = image.devicePixelRatio()
    color = image.pixelColor(round(20 * scale), round(pin.height() / 2 * scale))
    assert color.blue() < 100 and color.red() < 100 and color.green() < 100
