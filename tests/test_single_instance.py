from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from gaming_buddy.single_instance import InstanceError, SingleInstance

CHILD = """
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QTimer
from gaming_buddy.single_instance import SingleInstance
app = QCoreApplication([])
guard = SingleInstance(Path(sys.argv[1]))
primary = guard.claim_or_notify()
print('PRIMARY' if primary else 'SECONDARY', flush=True)
if primary:
    guard.activation_requested.connect(lambda: print('ACTIVATED', flush=True))
    QTimer.singleShot(int(sys.argv[2]), guard.set_ready)
    app.exec()
guard.close()
"""


@pytest.fixture(autouse=True)
def unchanged_application_state(qt_application):
    def state():
        return (
            qt_application.applicationName(),
            qt_application.organizationName(),
            qt_application.styleSheet(),
            qt_application.quitOnLastWindowClosed(),
            qt_application.windowIcon().cacheKey(),
        )

    before = state()
    yield
    assert state() == before, "Startup unit tests must not mutate the shared Qt application"


@pytest.fixture
def startup_application(monkeypatch):
    from unittest.mock import Mock

    import gaming_buddy.app as app_module

    application = Mock()
    monkeypatch.setattr(app_module, "QApplication", lambda _: application)
    monkeypatch.setattr(app_module, "QCoreApplication", Mock())
    monkeypatch.setattr(app_module, "QGuiApplication", Mock())
    return application


@pytest.fixture
def children():
    processes = []

    def start(path, delay=0):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", CHILD, str(path), str(delay)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        processes.append(process)
        lines = queue.Queue()

        def read():
            for line in process.stdout:
                lines.put(line.strip())
            lines.put("EXIT")

        threading.Thread(target=read, daemon=True).start()
        return process, lines

    yield start
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()


def line(lines):
    return lines.get(timeout=10)


def test_second_launch_activates_original_and_exits(tmp_path, children):
    primary, events = children(tmp_path)
    assert line(events) == "PRIMARY"
    secondary, second_events = children(tmp_path)
    assert line(second_events) == "SECONDARY"
    assert secondary.wait(timeout=5) == 0
    assert line(events) == "ACTIVATED"
    third, third_events = children(tmp_path)
    assert line(third_events) == "SECONDARY"
    assert third.wait(timeout=5) == 0
    assert line(events) == "ACTIVATED"
    assert primary.poll() is None


def test_simultaneous_launches_have_one_owner(tmp_path, children):
    first, first_events = children(tmp_path)
    second, second_events = children(tmp_path)
    results = [line(first_events), line(second_events)]
    assert sorted(results) == ["PRIMARY", "SECONDARY"]
    owner_events = first_events if results[0] == "PRIMARY" else second_events
    assert line(owner_events) == "ACTIVATED"
    secondary = second if results[0] == "PRIMARY" else first
    assert secondary.wait(timeout=5) == 0


def test_pending_activation_is_delivered_after_startup(tmp_path, children):
    _, events = children(tmp_path, delay=800)
    assert line(events) == "PRIMARY"
    secondary, second_events = children(tmp_path)
    assert line(second_events) == "SECONDARY"
    assert secondary.wait(timeout=5) == 0
    assert line(events) == "ACTIVATED"


def test_new_launch_recovers_after_owner_is_killed(tmp_path, children):
    primary, events = children(tmp_path)
    assert line(events) == "PRIMARY"
    primary.kill()
    primary.wait(timeout=5)
    replacement, replacement_events = children(tmp_path)
    assert line(replacement_events) == "PRIMARY"
    assert replacement.poll() is None


def test_unresponsive_owner_is_not_replaced(tmp_path):
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    lock = QLockFile(str(tmp_path / "instance.lock"))
    lock.setStaleLockTime(0)
    assert lock.tryLock(0)
    guard = SingleInstance(tmp_path, timeout_ms=100)
    try:
        with pytest.raises(InstanceError, match="not responding"):
            guard.claim_or_notify()
        guard.close()
        challenger = QLockFile(str(tmp_path / "instance.lock"))
        assert not challenger.tryLock(0)
        assert application is not None
    finally:
        lock.unlock()


def test_secondary_startup_does_not_open_storage_or_register_shortcuts(
    tmp_path,
    monkeypatch,
    startup_application,
):
    from unittest.mock import Mock

    import gaming_buddy.app as app_module

    guard = Mock()
    guard.claim_or_notify.return_value = False
    monkeypatch.setattr(app_module, "SingleInstance", lambda _: guard)
    monkeypatch.setattr(app_module, "ensure_data_dirs", lambda: (tmp_path, tmp_path))
    store = Mock(side_effect=AssertionError("Secondary instance must not open storage"))
    monkeypatch.setattr(app_module, "CardStore", store)
    monkeypatch.setattr(app_module, "Dashboard", store)
    monkeypatch.setattr(app_module, "GlobalHotkeys", store)
    assert app_module.main() == 0
    guard.close.assert_called_once()


def test_startup_failure_releases_the_instance_lock(tmp_path, monkeypatch, startup_application):
    from PySide6.QtCore import QLockFile

    import gaming_buddy.app as app_module

    monkeypatch.setattr(app_module, "ensure_data_dirs", lambda: (tmp_path, tmp_path))

    def failed_store(_path):
        challenger = QLockFile(str(tmp_path / "instance.lock"))
        assert not challenger.tryLock(0)
        raise RuntimeError("Storage failed")

    monkeypatch.setattr(app_module, "CardStore", failed_store)
    with pytest.raises(RuntimeError, match="Storage failed"):
        app_module.main()
    replacement = SingleInstance(tmp_path)
    try:
        assert replacement.claim_or_notify()
    finally:
        replacement.close()


@pytest.mark.parametrize("command", [b"BAD\n", b"SHOW\nextra", b"x" * 1000])
def test_invalid_requests_do_not_activate_or_block_owner(tmp_path, children, command):
    from PySide6.QtNetwork import QLocalSocket
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    _, events = children(tmp_path)
    assert line(events) == "PRIMARY"
    guard = SingleInstance(tmp_path)
    socket = QLocalSocket()
    try:
        socket.connectToServer(guard._name)
        assert socket.waitForConnected(2000)
        socket.write(command)
        socket.flush()
        assert not socket.waitForReadyRead(2000)
        assert events.empty()
        secondary, secondary_events = children(tmp_path)
        assert line(secondary_events) == "SECONDARY"
        assert secondary.wait(timeout=5) == 0
        assert line(events) == "ACTIVATED"
        assert application is not None
    finally:
        socket.abort()
        guard.close()


def test_clean_shutdown_releases_lock_and_close_is_idempotent(tmp_path):
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    guard = SingleInstance(tmp_path)
    assert guard.claim_or_notify()
    assert guard.claim_or_notify()
    guard.close()
    guard.close()
    replacement = SingleInstance(tmp_path)
    try:
        assert replacement.claim_or_notify()
        assert application is not None
    finally:
        replacement.close()


def test_existing_minimized_panel_is_restored():
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication, QWidget

    from gaming_buddy.dashboard import Dashboard

    application = QApplication.instance() or QApplication([])
    panel = QWidget()
    panel.game_detector = SimpleNamespace(poll_now=lambda: None)
    try:
        panel.showMinimized()
        application.processEvents()
        assert panel.isMinimized()
        Dashboard.show_panel(panel)
        application.processEvents()
        assert panel.isVisible()
        assert not panel.isMinimized()
    finally:
        panel.close()


def test_fragmented_activation_command_is_accepted(tmp_path, children):
    from PySide6.QtNetwork import QLocalSocket
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    _, events = children(tmp_path)
    assert line(events) == "PRIMARY"
    guard = SingleInstance(tmp_path)
    socket = QLocalSocket()
    try:
        socket.connectToServer(guard._name)
        assert socket.waitForConnected(2000)
        socket.write(b"SH")
        socket.flush()
        assert not socket.waitForReadyRead(50)
        socket.write(b"OW\n")
        socket.flush()
        assert socket.waitForReadyRead(2000)
        assert bytes(socket.readAll()) == b"OK\n"
        assert line(events) == "ACTIVATED"
        assert application is not None
    finally:
        socket.abort()
        guard.close()


def test_listen_failure_releases_lock(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    guard = SingleInstance(tmp_path)
    monkeypatch.setattr(guard._server, "listen", lambda _: False)
    with pytest.raises(InstanceError, match="local connection"):
        guard.claim_or_notify()
    replacement = SingleInstance(tmp_path)
    try:
        assert replacement.claim_or_notify()
        assert application is not None
    finally:
        replacement.close()
        guard.close()


def test_lock_access_error_is_reported_without_opening_storage(
    tmp_path,
    monkeypatch,
    startup_application,
):
    from unittest.mock import Mock

    import gaming_buddy.app as app_module

    guard = Mock()
    guard.claim_or_notify.side_effect = InstanceError("Check your data folder permissions.")
    monkeypatch.setattr(app_module, "SingleInstance", lambda _: guard)
    monkeypatch.setattr(app_module, "ensure_data_dirs", lambda: (tmp_path, tmp_path))
    monkeypatch.setattr(app_module, "CardStore", Mock(side_effect=AssertionError("Storage opened")))
    warnings = []
    monkeypatch.setattr(app_module.QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    assert app_module.main() == 1
    assert warnings == ["Check your data folder permissions."]
    guard.close.assert_called_once()
