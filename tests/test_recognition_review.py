import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QImage

from gaming_buddy.text_recognition import RecognitionLanguage, RecognitionResult
from gaming_buddy.text_recognition_dialog import TextRecognitionDialog


def wait_ready(dialog):
    if dialog.shutdown_ready:
        return
    loop = QEventLoop()
    dialog.work_finished.connect(loop.quit)
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    assert dialog.shutdown_ready


def test_review_waits_for_save_confirmation_and_keeps_literal_text(qt_application):
    dialog = TextRecognitionDialog(
        Path("capture.png"), "<b>CODE</b>\n0451", [], auto_start=False,
        confirm_save=True,
    )
    requests = []
    dialog.save_requested.connect(lambda: requests.append(dialog.recognized_text))
    dialog.show()
    try:
        assert dialog.preview.parentWidget() is dialog
        dialog.accept()
        assert dialog.isVisible()
        assert requests == ["<b>CODE</b>\n0451"]
        assert not dialog.text.acceptRichText()
        dialog.status.setText("Could not save. Try again.")
        dialog.text.setPlainText("Corrected\n0451")
        dialog.accept()
        assert dialog.isVisible() and len(requests) == 2
        dialog.confirm_saved()
        assert not dialog.isVisible() and dialog.result() == 1
    finally:
        dialog.close()
        dialog.deleteLater()


def test_language_discovery_and_recognition_run_off_gui_and_drain_on_shutdown(qt_application):
    main_thread = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    calls = []

    def languages():
        assert threading.get_ident() != main_thread
        started.set()
        if not release.wait(3):
            raise TimeoutError("Test did not release language discovery")
        return [RecognitionLanguage("it-IT", "Italian")]

    def recognize(path, language):
        calls.append((path, language, threading.get_ident()))
        return RecognitionResult("Porta 0451", language)

    dialog = TextRecognitionDialog(
        Path("clue.png"), "", [], "it-IT", recognizer=recognize,
        language_provider=languages, auto_start=False,
    )
    try:
        dialog.start_recognition()
        assert started.wait(3)
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qt_application.processEvents()
        assert heartbeat == [True]
        assert not dialog.language.isEnabled()
        assert dialog.text.isReadOnly()
        dialog.begin_shutdown()
        assert not dialog.shutdown_ready
        release.set()
        wait_ready(dialog)
        assert len(calls) == 1 and calls[0][:2] == (Path("clue.png"), "it-IT")
        assert calls[0][2] != main_thread
        assert dialog.selected_language == "it-IT"
        assert dialog.recognized_text == "Porta 0451"
        assert not dialog.recognize_button.isEnabled()
    finally:
        release.set()
        wait_ready(dialog)
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("failure", ["missing", "error"])
def test_unavailable_languages_preserve_text_and_allow_retry_or_manual_save(qt_application, failure):
    attempts = []

    def languages():
        attempts.append(True)
        if len(attempts) == 1:
            if failure == "error":
                raise RuntimeError("Language lookup unavailable")
            return []
        return [RecognitionLanguage("en-US", "English")]

    dialog = TextRecognitionDialog(
        Path("clue.png"), "Previous text", [], "xx-XX",
        language_provider=languages,
        recognizer=lambda _, language: RecognitionResult("Read again", language),
        auto_start=False,
    )
    try:
        dialog.start_recognition()
        wait_ready(dialog)
        assert dialog.recognized_text == "Previous text"
        assert "Could not recognize text" in dialog.status.text()
        assert dialog.recognize_button.isEnabled()
        assert not dialog.text.isReadOnly()
        dialog.start_recognition()
        wait_ready(dialog)
        assert dialog.recognized_text == "Read again"
        assert dialog.selected_language == ""
        assert len(attempts) == 2
    finally:
        wait_ready(dialog)
        dialog.close()
        dialog.deleteLater()


def test_preview_uses_saved_image_without_changing_original(qt_application, tmp_path):
    path = tmp_path / "capture.png"
    image = QImage(640, 360, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    assert image.save(str(path))
    original = path.read_bytes()
    dialog = TextRecognitionDialog(path, "", [], auto_start=False, preview_image=True)
    try:
        assert not dialog.preview.pixmap().isNull()
        assert "640 × 360" in dialog.preview.toolTip()
        assert dialog.preview.pixmap().height() <= 140
        assert path.read_bytes() == original
    finally:
        dialog.close()
        dialog.deleteLater()
