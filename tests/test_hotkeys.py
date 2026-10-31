import pytest

import gaming_buddy.hotkeys as hotkeys_module
from gaming_buddy.hotkeys import (
    DEFAULT_SHORTCUTS,
    GlobalHotkeys,
    parse_shortcut,
    shortcut_hooks,
    validate_shortcuts,
)


def test_default_shortcuts_are_valid():
    assert validate_shortcuts(DEFAULT_SHORTCUTS) == DEFAULT_SHORTCUTS
    assert shortcut_hooks(DEFAULT_SHORTCUTS) == {
        "toggle_panel": "<ctrl>+<shift>+g",
        "toggle_quick_panel": "<ctrl>+<shift>+q",
        "quick_finder": "<ctrl>+<shift>+f",
        "capture_area": "<ctrl>+<shift>+s",
        "capture_screen": "<ctrl>+<shift>+d",
        "toggle_click_through": "<ctrl>+<shift>+l",
        "toggle_focus_mode": "<ctrl>+<shift>+m",
        "previous_pin": "<ctrl>+<shift>+<left>",
        "next_pin": "<ctrl>+<shift>+<right>",
        "restore_pins": "<ctrl>+<shift>+<up>",
    }


def test_shortcut_is_normalized_for_display_and_listener():
    assert parse_shortcut("shift+alt+f12") == ("Alt+Shift+F12", "<alt>+<shift>+<f12>")
    assert parse_shortcut("Ctrl+Page Up") == ("Ctrl+Page Up", "<ctrl>+<page_up>")


@pytest.mark.parametrize("shortcut", ["", "G", "Ctrl+Shift", "Ctrl+Shift+G+H"])
def test_invalid_shortcuts_are_rejected(shortcut):
    with pytest.raises(ValueError):
        parse_shortcut(shortcut)


def test_duplicate_shortcuts_are_rejected():
    duplicates = DEFAULT_SHORTCUTS | {"capture_area": "shift+ctrl+g"}
    with pytest.raises(ValueError, match="already assigned"):
        validate_shortcuts(duplicates)


def test_listener_status_tracks_start_stop_and_failure(monkeypatch):
    class Listener:
        def __init__(self, hooks):
            self.alive = False

        def start(self):
            self.alive = True

        def stop(self):
            self.alive = False

        def is_alive(self):
            return self.alive

    monkeypatch.setattr(hotkeys_module.keyboard, "GlobalHotKeys", Listener)
    hotkeys = GlobalHotkeys()
    assert not hotkeys.running
    hotkeys.start()
    assert hotkeys.running
    hotkeys.stop()
    assert not hotkeys.running

    def unavailable(hooks):
        raise RuntimeError("Hook not available")

    monkeypatch.setattr(hotkeys_module.keyboard, "GlobalHotKeys", unavailable)
    failures = []
    hotkeys.failed.connect(failures.append)
    hotkeys.start()
    assert not hotkeys.running
    assert failures == ["Hook not available"]


def test_full_monitor_shortcut_emits_its_own_action(monkeypatch):
    callbacks = {}
    class Listener:
        def __init__(self, hooks):
            callbacks.update(hooks)
        def start(self):
            pass
        def stop(self):
            pass
    monkeypatch.setattr(hotkeys_module.keyboard, "GlobalHotKeys", Listener)
    hotkeys = GlobalHotkeys()
    fired = []
    hotkeys.capture_screen.connect(lambda: fired.append("screen"))
    hotkeys.capture_area.connect(lambda: fired.append("area"))
    hotkeys.start()
    callbacks["<ctrl>+<shift>+d"]()
    assert fired == ["screen"]
    hotkeys.stop()


def test_shutdown_waits_for_stopped_listener_and_prevents_restart(monkeypatch):
    listeners = []

    class Listener:
        def __init__(self, hooks):
            self.alive = False
            listeners.append(self)

        def start(self):
            self.alive = True

        def stop(self):
            pass  # Real hook cleanup can finish after stop() returns.

        def is_alive(self):
            return self.alive

    monkeypatch.setattr(hotkeys_module.keyboard, "GlobalHotKeys", Listener)
    hotkeys = GlobalHotkeys()
    hotkeys.start()
    hotkeys.begin_shutdown()
    assert not hotkeys.running
    assert not hotkeys.shutdown_ready
    hotkeys.start()
    assert len(listeners) == 1
    listeners[0].alive = False
    assert hotkeys.shutdown_ready
    hotkeys.cancel_shutdown()
    assert hotkeys.running
    assert len(listeners) == 2
    listeners[1].alive = False
    hotkeys.stop()


def test_shortcut_resume_requested_during_exit_runs_after_exit_is_cancelled(monkeypatch):
    class Listener:
        def __init__(self, hooks):
            self.alive = False

        def start(self):
            self.alive = True

        def stop(self):
            self.alive = False

        def is_alive(self):
            return self.alive

    monkeypatch.setattr(hotkeys_module.keyboard, "GlobalHotKeys", Listener)
    hotkeys = GlobalHotkeys()
    hotkeys.begin_shutdown()
    hotkeys.start()  # A settings dialog may request restart while exit is pending.
    assert not hotkeys.running
    hotkeys.cancel_shutdown()
    assert hotkeys.running
    hotkeys.stop()
