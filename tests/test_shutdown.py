from PySide6.QtTest import QSignalSpy

from gaming_buddy.shutdown import ShutdownController


def test_idle_exit_finishes_once(qt_application):
    controller = ShutdownController(lambda: True)
    finished = QSignalSpy(controller.finished)
    controller.request()
    controller.request()
    assert finished.count() == 1
    assert not controller.active


def test_exit_waits_for_tasks_with_a_running_gui_event_loop(qt_application):
    ready = [False]
    controller = ShutdownController(lambda: ready[0], poll_ms=10)
    finished = QSignalSpy(controller.finished)
    controller.request()
    controller.request()
    assert controller.active
    assert finished.count() == 0
    ready[0] = True
    assert finished.wait(1000)
    assert finished.count() == 1


def test_cancel_exit_stops_polling_and_allows_retry(qt_application):
    ready = [False]
    controller = ShutdownController(lambda: ready[0], poll_ms=10)
    finished = QSignalSpy(controller.finished)
    cancelled = QSignalSpy(controller.cancelled)
    controller.request()
    controller.cancel()
    controller.cancel()
    assert not controller.active
    assert cancelled.count() == 1
    ready[0] = True
    qt_application.processEvents()
    assert finished.count() == 0
    controller.request()
    assert finished.count() == 1


def test_timeout_leaves_live_workers_untouched_and_does_not_quit(qt_application):
    clock = [0.0]
    controller = ShutdownController(lambda: False, timeout_ms=50, clock=lambda: clock[0])
    finished = QSignalSpy(controller.finished)
    timed_out = QSignalSpy(controller.timed_out)
    controller.request()
    clock[0] = 0.051
    controller._poll()
    assert not controller.active
    assert finished.count() == 0
    assert timed_out.count() == 1
