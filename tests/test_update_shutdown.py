from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

import gaming_buddy.updates as updates_module
from gaming_buddy.updates import ReleaseAsset, ReleaseInfo, UpdateCancelled, UpdateController


class WorkerGate:
    """Hold a real worker until the test releases it, and always join it afterward."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.worker: threading.Thread | None = None

    def block(self) -> None:
        self.worker = threading.current_thread()
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("The test did not release the update worker.")

    def join(self) -> None:
        self.release.set()
        if self.worker is not None:
            self.worker.join(5)
            assert not self.worker.is_alive(), "The update worker did not finish."


@pytest.fixture
def worker_gate() -> Iterator[WorkerGate]:
    gate = WorkerGate()
    try:
        yield gate
    finally:
        gate.join()


@pytest.fixture
def release_info() -> ReleaseInfo:
    installer = ReleaseAsset("setup.exe", "https://example.test/setup.exe", 1)
    checksum = ReleaseAsset("setup.exe.sha256", "https://example.test/setup.exe.sha256", 1)
    return ReleaseInfo(
        "99.0.0", "v99.0.0", "Test release", "", "https://example.test/release", "",
        installer, checksum,
    )


def test_idle_shutdown_is_ready_and_repeated_requests_are_safe() -> None:
    controller = UpdateController()

    controller.begin_shutdown()
    controller.begin_shutdown()

    assert controller.shutdown_ready


def test_shutdown_rejects_new_operations_even_when_idle(
    release_info: ReleaseInfo,
    tmp_path: Path,
) -> None:
    controller = UpdateController()
    controller.begin_shutdown()

    assert not controller.check_for_updates()
    assert not controller.download_update(release_info, tmp_path)
    assert not controller.checking
    assert not controller.downloading


def test_shutdown_waits_for_an_update_check_to_finish(
    monkeypatch: pytest.MonkeyPatch,
    worker_gate: WorkerGate,
    release_info: ReleaseInfo,
) -> None:
    def fetch() -> ReleaseInfo:
        worker_gate.block()
        return release_info

    monkeypatch.setattr(updates_module, "fetch_latest_release", fetch)
    controller = UpdateController()
    assert controller.check_for_updates()
    assert worker_gate.started.wait(5)

    controller.begin_shutdown()

    assert not controller.shutdown_ready
    assert not controller.check_for_updates()
    worker_gate.join()
    assert controller.shutdown_ready


def test_shutdown_readiness_tracks_worker_exit_not_only_the_checking_flag(
    monkeypatch: pytest.MonkeyPatch,
    worker_gate: WorkerGate,
    release_info: ReleaseInfo,
) -> None:
    monkeypatch.setattr(updates_module, "fetch_latest_release", lambda: release_info)
    controller = UpdateController()
    # A direct result subscriber runs inside the worker after checking becomes False.
    controller.update_available.connect(worker_gate.block, Qt.ConnectionType.DirectConnection)
    assert controller.check_for_updates()
    assert worker_gate.started.wait(5)
    assert not controller.checking

    controller.begin_shutdown()

    assert not controller.shutdown_ready
    worker_gate.join()
    assert controller.shutdown_ready


def test_shutdown_cancels_download_but_waits_for_the_backend_to_finish(
    monkeypatch: pytest.MonkeyPatch,
    worker_gate: WorkerGate,
    release_info: ReleaseInfo,
    tmp_path: Path,
) -> None:
    cancellations: list[threading.Event] = []

    def download(
        _release: ReleaseInfo,
        _destination: Path,
        *,
        cancelled: threading.Event,
        **_kwargs: object,
    ) -> Path:
        cancellations.append(cancelled)
        worker_gate.block()
        if cancelled.is_set():
            raise UpdateCancelled("Update download cancelled.")
        return tmp_path / "setup.exe"

    monkeypatch.setattr(updates_module, "download_release", download)
    controller = UpdateController()
    assert controller.download_update(release_info, tmp_path)
    assert worker_gate.started.wait(5)

    controller.begin_shutdown()
    controller.begin_shutdown()

    assert cancellations[0].is_set()
    assert not controller.shutdown_ready
    assert not controller.download_update(release_info, tmp_path)
    worker_gate.join()
    assert controller.shutdown_ready


@pytest.mark.parametrize("operation", ["check", "download"])
def test_cancelling_shutdown_restores_admission_after_the_old_worker_finishes(
    monkeypatch: pytest.MonkeyPatch,
    worker_gate: WorkerGate,
    release_info: ReleaseInfo,
    tmp_path: Path,
    operation: str,
) -> None:
    def fetch() -> ReleaseInfo:
        worker_gate.block()
        return release_info

    def download(
        _release: ReleaseInfo,
        _destination: Path,
        **_kwargs: object,
    ) -> Path:
        worker_gate.block()
        return tmp_path / "setup.exe"

    monkeypatch.setattr(updates_module, "fetch_latest_release", fetch)
    monkeypatch.setattr(updates_module, "download_release", download)
    controller = UpdateController()

    def start() -> bool:
        if operation == "check":
            return controller.check_for_updates()
        return controller.download_update(release_info, tmp_path)

    assert start()
    assert worker_gate.started.wait(5)
    controller.begin_shutdown()
    controller.cancel_shutdown()
    assert not start(), "An existing task must still prevent an overlapping operation."
    worker_gate.join()

    worker_gate.started.clear()
    assert start()
    assert worker_gate.started.wait(5)
    worker_gate.join()
    controller.begin_shutdown()
    assert controller.shutdown_ready
