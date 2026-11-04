import sqlite3
import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QSettings, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialog

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.quick_finder import find_cards
from gaming_buddy.storage import CardStore
from gaming_buddy.text_recognition import RecognitionLanguage, RecognitionResult
from gaming_buddy.text_recognition_dialog import TextRecognitionDialog


def wait_ready(dialog):
    if not dialog.shutdown_ready:
        loop = QEventLoop()
        dialog.work_finished.connect(loop.quit)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
    assert dialog.shutdown_ready


@pytest.fixture
def host(qt_application, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    settings.setValue("capture/notifications", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    monkeypatch.setattr(dashboard_module, "available_languages",
                        lambda: [RecognitionLanguage("en-US", "English")])

    def review(*args, **kwargs):
        return TextRecognitionDialog(
            *args, **kwargs, auto_start=False,
            recognizer=lambda _, language: RecognitionResult("Door code 0451", language),
        )

    monkeypatch.setattr(dashboard_module, "TextRecognitionDialog", review)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        dashboard = Dashboard(store, tmp_path / "captures")
        for timer in dashboard._startup_timers:
            timer.stop()
        yield dashboard
        dialog = dashboard._text_recognition_dialog
        if dialog is not None:
            dialog.begin_shutdown()
            wait_ready(dialog)
            dialog.reject()
        dashboard.note_draft_timer.stop()
        dashboard._capture_timer.stop()
        dashboard.game_detector.stop()
        for pin in dashboard.pins.values():
            pin.discard_pending_layout()
            pin.close()
            pin.deleteLater()
        dashboard.tray.hide()
        dashboard._really_quit = True
        dashboard.close()
        dashboard.deleteLater()
        qt_application.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def image():
    result = QImage(320, 180, QImage.Format.Format_RGB32)
    result.fill(Qt.GlobalColor.blue)
    return result


def saved_image(host):
    host.captures_dir.mkdir(exist_ok=True)
    path = host.captures_dir / "existing.png"
    assert image().save(str(path))
    card = Card(None, CardKind.IMAGE, "Puzzle", "A clue", content="Old text", image_path=str(path))
    host.store.add(card)
    return card


@pytest.mark.parametrize("failure", ["exception", "unavailable"])
def test_review_save_failure_preserves_corrections_and_can_retry(host, monkeypatch, failure):
    card = saved_image(host)
    host._extract_image_text(card)
    dialog = host._text_recognition_dialog
    dialog.text.setPlainText("Corrected clue\n0451")

    def fail(*_, **__):
        if failure == "exception":
            raise sqlite3.OperationalError("disk full")
        return False

    with monkeypatch.context() as patch:
        patch.setattr(host.store, "update_details", fail)
        dialog.accept()
        assert dialog.isVisible()
        assert dialog.recognized_text == "Corrected clue\n0451"
        assert "not be saved" in dialog.status.text()
        assert host.store.get(card.id).content == "Old text"
    dialog.accept()
    assert host._text_recognition_dialog is None
    assert host.store.get(card.id).content == "Corrected clue\n0451"
    assert len(host.store.list()) == 1


def test_background_language_lookup_then_explicit_save_preserves_current_metadata(host, monkeypatch):
    threads = []

    def languages():
        threads.append(threading.get_ident())
        return [RecognitionLanguage("en-US", "English")]

    monkeypatch.setattr(dashboard_module, "available_languages", languages)
    card = saved_image(host)
    host._extract_image_text(card)
    assert not threads
    dialog = host._text_recognition_dialog
    dialog.start_recognition()
    wait_ready(dialog)
    assert threads and threads[0] != threading.get_ident()
    assert host.store.get(card.id).content == "Old text"
    host.store.update_details(card.id, title="Renamed clue", game="Different game", content="Old text")
    dialog.accept()
    stored = host.store.get(card.id)
    assert (stored.title, stored.game, stored.content) == (
        "Renamed clue", "Different game", "Door code 0451",
    )
    assert host._recognition_languages == [RecognitionLanguage("en-US", "English")]
    assert host.store.list(query="0451")[0].id == card.id


def test_deleted_card_stays_open_for_copy_without_saving_elsewhere(host):
    card = saved_image(host)
    host._extract_image_text(card)
    dialog = host._text_recognition_dialog
    dialog.text.setPlainText("Keep this clue")
    host.store.move_to_trash(card.id)
    dialog.accept()
    assert dialog.isVisible()
    assert "no longer available" in dialog.status.text()
    assert not host.store.list()
    dialog.copy_text()
    assert dialog.recognized_text == "Keep this clue"


def test_cancel_does_not_write_recognized_text(host):
    card = saved_image(host)
    host._extract_image_text(card)
    dialog = host._text_recognition_dialog
    dialog.text.setPlainText("Discard this result")
    dialog.reject()
    assert host.store.get(card.id).content == "Old text"


@pytest.mark.parametrize("action", ["save_and_pin", "save_only", "review"])
def test_capture_text_saves_one_original_and_reviews_without_changing_preferences(host, action):
    host.settings.setValue("capture/action", action)
    host.settings.setValue("capture/keep_panel_hidden", True)
    host.note_input.setPlainText("Keep my note draft")
    host.show()
    host.start_text_capture()
    assert host.capture_text.pending and host._capture_in_progress
    assert not host.isVisible()
    host._capture_timer.stop()
    original = image()
    host._save_capture(original)
    dialog = host._text_recognition_dialog
    assert dialog.isVisible() and not dialog.preview.pixmap().isNull()
    assert not host.capture_text.pending
    cards = host.store.list()
    assert len(cards) == 1 and not cards[0].pinned
    assert QImage(cards[0].image_path) == original
    assert host.settings.value("capture/action") == action
    assert host.note_input.toPlainText() == "Keep my note draft"
    assert not host.isVisible()
    dialog.start_recognition()
    wait_ready(dialog)
    assert host.store.get(cards[0].id).content == ""
    dialog.accept()
    assert len(host.store.list()) == 1
    assert find_cards(host.store.list(), "0451")[0].id == cards[0].id


@pytest.mark.parametrize("terminal", ["cancel", "failure", "quit"])
def test_capture_text_intent_clears_before_next_normal_capture(host, monkeypatch, terminal):
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)
    host.start_text_capture()
    host._capture_timer.stop()
    if terminal == "cancel":
        host._capture_cancelled()
    elif terminal == "failure":
        host._capture_failed("Controlled capture failure")
    else:
        host._stop_deferred_work()
    assert not host.capture_text.pending
    assert not host.store.list() and host._text_recognition_dialog is None
    host.settings.setValue("capture/action", "save_only")
    host.start_capture()
    host._capture_timer.stop()
    host._save_capture(image())
    assert len(host.store.list()) == 1 and host._text_recognition_dialog is None


def test_capture_text_from_quick_panel_and_existing_review_is_reused(host):
    host.show_quick_panel()
    quick = host.quick_panel.panel
    quick.capture_button.text_action.trigger()
    assert host._capture_in_progress and not quick.isVisible()
    host._capture_timer.stop()
    host._save_capture(image())
    dialog = host._text_recognition_dialog
    dialog.hide()
    host.start_text_capture()
    assert host._text_recognition_dialog is dialog and dialog.isVisible()
    assert not host._capture_in_progress
    assert not host.capture_text.pending


def test_capture_text_obeys_busy_and_shutdown_guards(host):
    host._quitting = True
    host.start_text_capture()
    assert not host.capture_text.pending
    host._quitting = False
    host._card_pack_dialog = object()
    host.start_text_capture()
    assert not host.capture_text.pending
    host._card_pack_dialog = None
    host.start_capture()
    host._capture_timer.stop()
    host.start_text_capture()
    assert host._capture_in_progress and not host.capture_text.pending
    host._capture_cancelled()


def test_failed_image_save_resets_intent_and_does_not_open_review(host, monkeypatch):
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_: None)

    def fail(_):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(host.store, "add", fail)
    host.start_text_capture()
    host._capture_timer.stop()
    host._save_capture(image())
    assert not host.capture_text.pending
    assert host._text_recognition_dialog is None
    assert not host.store.list()
    assert not list(host.captures_dir.glob("*.png"))


def test_modal_blocks_text_capture_and_review_during_selection(host, qt_application):
    modal = QDialog(host)
    modal.setModal(True)
    modal.show()
    qt_application.processEvents()
    host.start_text_capture()
    assert not host.capture_text.pending and not host._capture_in_progress
    modal.reject()
    modal.deleteLater()
    card = saved_image(host)
    host.start_capture()
    host._capture_timer.stop()
    host._extract_image_text(card)
    assert host._text_recognition_dialog is None
    host._capture_cancelled()
