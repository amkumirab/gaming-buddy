import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QTimer

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.card_editor import CardEditor
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.mark.parametrize("retry", [False, True])
def test_failed_editor_save_keeps_fields_for_retry_and_releases_finished_dialog(
    qt_application, tmp_path, monkeypatch, retry,
):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(Card(None, CardKind.NOTE, "Puzzle", "Old title", content="Old clue"))
        store._connection.execute(
            "CREATE TRIGGER reject_tag BEFORE INSERT ON card_tags "
            "WHEN NEW.tag = 'rejected' BEGIN SELECT RAISE(ABORT, 'controlled tag failure'); END"
        )
        store._connection.commit()
        host = Dashboard(store, tmp_path / "captures")
        for timer in host._startup_timers:
            timer.stop()
        editor = CardEditor(card, host)
        editor.title_input.setText("Changed title")
        editor.tags_input.setText("rejected")
        editor.content_input.setPlainText("Changed clue\n\nKeep this text")
        monkeypatch.setattr(dashboard_module, "CardEditor", lambda *_: editor)
        warnings = []

        def warning(*_):
            warnings.append(True)
            assert editor.content_input.toPlainText() == "Changed clue\n\nKeep this text"
            assert editor.tags_input.text() == "rejected"
            if retry:
                store._connection.execute("DROP TRIGGER reject_tag")
                store._connection.commit()
            QTimer.singleShot(0, editor.accept if retry else editor.reject)

        monkeypatch.setattr(dashboard_module.QMessageBox, "warning", warning)
        try:
            QTimer.singleShot(0, editor.accept)
            host._edit_card(card)
            assert warnings == [True]
            assert store.get(card.id).content == ("Changed clue\n\nKeep this text" if retry else "Old clue")
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert not host.findChildren(CardEditor)
        finally:
            host.note_draft_timer.stop()
            host.game_detector.stop()
            host.tray.hide()
            host._really_quit = True
            host.close()
            host.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
