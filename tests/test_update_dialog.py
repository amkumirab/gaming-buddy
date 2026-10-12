from __future__ import annotations

import os
import subprocess
import sys
import threading
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QPushButton

import gaming_buddy.updates as update_module
from gaming_buddy.update_dialog import UpdateAction, UpdateDialog
from gaming_buddy.updates import ReleaseAsset, ReleaseInfo, UpdateController


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_update_button_callbacks_do_not_retain_closed_dialog(application):
    release = SimpleNamespace(version="0.2.0", title="Update", notes="Release notes")
    dialog = UpdateDialog("0.1.0", release)
    reference = weakref.ref(dialog)
    dialog.close()
    del dialog
    assert reference() is None


def test_closed_update_dialog_allows_native_qt_shutdown():
    script = """
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from gaming_buddy.update_dialog import UpdateAction, UpdateDialog

application = QApplication([])
dialog = UpdateDialog('0.1.0', SimpleNamespace(version='0.2.0', title='Update', notes=''))
dialog._choose(UpdateAction.DOWNLOAD)
del dialog
application.shutdown()
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        capture_output=True, text=True, env=environment, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("label", "action"),
    [
        ("View release page", UpdateAction.VIEW_RELEASE),
        ("Download and install", UpdateAction.DOWNLOAD),
    ],
)
def test_update_buttons_choose_the_expected_action(application, label, action):
    release = SimpleNamespace(version="0.2.0", title="Update", notes="Release notes")
    dialog = UpdateDialog("0.1.0", release)
    button = next(button for button in dialog.findChildren(QPushButton) if button.text() == label)
    button.click()
    assert dialog.action is action
    assert dialog.result() == dialog.DialogCode.Accepted


def test_update_dialog_shows_versions_notes_and_explicit_action(
    application: QApplication,
) -> None:
    installer = ReleaseAsset("setup.exe", "https://example.com/setup.exe", 100)
    checksum = ReleaseAsset("setup.exe.sha256", "https://example.com/setup.sha256", 100)
    release = ReleaseInfo(
        "1.2.3",
        "v1.2.3",
        "Gaming Buddy 1.2.3",
        "Release notes",
        "https://example.com/release",
        "2026-09-09T08:00:00Z",
        installer,
        checksum,
    )
    dialog = UpdateDialog("1.0.0", release)
    labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
    notes = dialog.findChild(QPlainTextEdit)

    assert "Installed: 1.0.0" in labels
    assert "Available: 1.2.3" in labels
    assert notes is not None and notes.toPlainText() == "Release notes"
    assert dialog.action is None
    dialog._choose(UpdateAction.DOWNLOAD)
    assert dialog.action is UpdateAction.DOWNLOAD


def test_update_controller_reports_a_newer_release_without_blocking_ui(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = ReleaseAsset("setup.exe", "https://example.com/setup.exe", 100)
    checksum = ReleaseAsset("setup.exe.sha256", "https://example.com/setup.sha256", 100)
    release = ReleaseInfo(
        "1.2.3",
        "v1.2.3",
        "Gaming Buddy 1.2.3",
        "Release notes",
        "https://example.com/release",
        "2026-09-09T08:00:00Z",
        installer,
        checksum,
    )
    allow_response = threading.Event()

    def fetch_release() -> ReleaseInfo:
        allow_response.wait(timeout=1)
        return release

    monkeypatch.setattr(update_module, "fetch_latest_release", fetch_release)
    controller = UpdateController()
    received: list[ReleaseInfo] = []
    checking_on_result: list[bool] = []
    loop = QEventLoop()
    controller.update_available.connect(
        lambda _release: checking_on_result.append(controller.checking),
        Qt.ConnectionType.DirectConnection,
    )
    controller.update_available.connect(received.append)
    controller.update_available.connect(lambda _release: loop.quit())

    assert controller.check_for_updates() is True
    assert controller.check_for_updates() is False
    allow_response.set()
    QTimer.singleShot(2_000, loop.quit)
    loop.exec()

    assert received == [release]
    assert checking_on_result == [False]
    assert controller.checking is False
