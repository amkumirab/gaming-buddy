from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from gaming_buddy.text_recognition import RecognitionLanguage, RecognitionResult
from gaming_buddy.text_recognition_dialog import TextRecognitionDialog


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def _dialog() -> TextRecognitionDialog:
    return TextRecognitionDialog(
        Path("capture.png"),
        "Previously saved text",
        [
            RecognitionLanguage("en-US", "English (United States)"),
            RecognitionLanguage("it-IT", "Italian (Italy)"),
        ],
        "it-IT",
        auto_start=False,
    )


def test_dialog_restores_language_and_existing_text(application: QApplication) -> None:
    dialog = _dialog()

    assert dialog.selected_language == "it-IT"
    assert dialog.recognized_text == "Previously saved text"
    assert dialog.text.isReadOnly() is False
    dialog.close()


def test_dialog_displays_recognition_result(application: QApplication) -> None:
    dialog = _dialog()

    dialog._recognition_succeeded(RecognitionResult("SAFE CODE 0451", "en-US"))

    assert dialog.recognized_text == "SAFE CODE 0451"
    assert dialog.status.text() == "Text recognized using en-US."
    dialog.close()


def test_dialog_handles_empty_result_and_failure(application: QApplication) -> None:
    dialog = _dialog()

    dialog._recognition_succeeded(RecognitionResult("", "en-US"))
    assert "No readable text" in dialog.status.text()

    dialog._recognition_failed("Unsupported image")
    assert dialog.status.text() == "Could not recognize text: Unsupported image"
    dialog.close()


def test_dialog_copies_reviewed_text(application: QApplication) -> None:
    dialog = _dialog()
    dialog.text.setPlainText("  Corrected clue  ")

    dialog.copy_text()

    assert QApplication.clipboard().text() == "Corrected clue"
    assert dialog.status.text() == "Text copied to the clipboard."
    dialog.close()


def test_dialog_runs_recognition_without_blocking_controls_forever(
    application: QApplication,
) -> None:
    calls: list[tuple[Path, str]] = []

    def recognize(image_path: Path, language: str) -> RecognitionResult:
        calls.append((image_path, language))
        return RecognitionResult("Basement map", language)

    dialog = TextRecognitionDialog(
        Path("capture.png"),
        "",
        [RecognitionLanguage("en-US", "English (United States)")],
        "en-US",
        recognizer=recognize,
        auto_start=False,
    )

    dialog.start_recognition()
    assert dialog.recognize_button.isEnabled() is False
    thread = dialog._thread
    assert thread is not None
    loop = QEventLoop()
    thread.finished.connect(loop.quit)
    QTimer.singleShot(2_000, loop.quit)
    loop.exec()
    application.processEvents()

    assert dialog._thread is None
    assert calls == [(Path("capture.png"), "en-US")]
    assert dialog.recognized_text == "Basement map"
    assert dialog.recognize_button.isEnabled() is True
    dialog.close()
