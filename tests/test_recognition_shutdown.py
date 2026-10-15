from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from gaming_buddy.text_recognition import RecognitionResult
from gaming_buddy.text_recognition_dialog import TextRecognitionDialog


def wait_until(predicate, timeout_ms=3000):
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)

    def check():
        if predicate():
            loop.quit()

    poll.timeout.connect(check)
    limit = QTimer()
    limit.setSingleShot(True)
    limit.timeout.connect(loop.quit)
    poll.start()
    limit.start(timeout_ms)
    if not predicate():
        loop.exec()
    poll.stop()
    limit.stop()
    assert predicate(), "Background work did not finish within the test deadline"


def test_shutdown_cancels_pending_recognition_auto_start(qt_application):
    assert hasattr(TextRecognitionDialog, "begin_shutdown")
    calls = []

    def recognize(path, language):
        calls.append(path)
        return RecognitionResult("Clue", language)

    dialog = TextRecognitionDialog(Path("capture.png"), "", [], recognizer=recognize)
    try:
        dialog.begin_shutdown()
        qt_application.processEvents()
        assert dialog.shutdown_ready
        assert calls == []
        dialog.start_recognition()
        assert calls == []
    finally:
        wait_until(lambda: dialog.shutdown_ready)
        dialog.close()


def test_shutdown_waits_for_recognition_without_blocking_gui(qt_application):
    assert hasattr(TextRecognitionDialog, "begin_shutdown")
    started = threading.Event()
    release = threading.Event()

    def recognize(_path, language):
        started.set()
        if not release.wait(3):
            raise TimeoutError("Recognition test was not released")
        return RecognitionResult("Reviewed clue", language)

    dialog = TextRecognitionDialog(
        Path("capture.png"), "", [], recognizer=recognize, auto_start=False,
    )
    heartbeat = []
    try:
        dialog.start_recognition()
        assert started.wait(3)
        dialog.begin_shutdown()
        assert not dialog.shutdown_ready
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qt_application.processEvents()
        assert heartbeat == [True]
        dialog.accept()
        assert dialog.result() == 0
        release.set()
        wait_until(lambda: dialog.shutdown_ready)
        assert dialog.recognized_text == "Reviewed clue"
        assert not dialog.recognize_button.isEnabled()
    finally:
        release.set()
        wait_until(lambda: dialog.shutdown_ready)
        dialog.close()


def test_cancelled_exit_allows_recognition_again(qt_application):
    assert hasattr(TextRecognitionDialog, "begin_shutdown")
    calls = []

    def recognize(path, language):
        calls.append(path)
        return RecognitionResult("Clue", language)

    dialog = TextRecognitionDialog(
        Path("capture.png"), "", [], recognizer=recognize, auto_start=False,
    )
    try:
        dialog.begin_shutdown()
        dialog.cancel_shutdown()
        dialog.start_recognition()
        wait_until(lambda: dialog.shutdown_ready)
        assert len(calls) == 1
        assert dialog.recognize_button.isEnabled()
        assert dialog.shutdown_ready
    finally:
        wait_until(lambda: dialog.shutdown_ready)
        dialog.close()


@pytest.mark.parametrize("action", ["close", "reject"])
def test_closed_dialog_does_not_start_queued_recognition(qt_application, action):
    calls = []

    def recognize(path, language):
        calls.append(path)
        return RecognitionResult("Clue", language)

    dialog = TextRecognitionDialog(Path("capture.png"), "", [], recognizer=recognize)
    try:
        getattr(dialog, action)()
        assert not dialog._auto_start_timer.isActive()
        qt_application.processEvents()
        assert calls == []
    finally:
        dialog.begin_shutdown()
        wait_until(lambda: dialog.shutdown_ready)
        dialog.close()
