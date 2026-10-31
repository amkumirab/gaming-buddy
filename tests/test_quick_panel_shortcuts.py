import gaming_buddy.hotkeys as hotkeys_module
from gaming_buddy.hotkeys import (
    DEFAULT_SHORTCUTS,
    GlobalHotkeys,
    complete_shortcuts,
    shortcut_hooks,
)


def test_upgrade_preserves_a_custom_binding_using_the_new_default():
    saved = {k: v for k, v in DEFAULT_SHORTCUTS.items() if k != "toggle_quick_panel"}
    saved["capture_area"] = "Ctrl+Shift+Q"
    upgraded = complete_shortcuts(saved)
    assert upgraded["capture_area"] == "Ctrl+Shift+Q"
    assert upgraded["toggle_quick_panel"] != "Ctrl+Shift+Q"
    assert len(set(shortcut_hooks(upgraded).values())) == len(upgraded)


def test_both_missing_actions_are_upgraded_without_stealing_saved_keys():
    saved = {k: v for k, v in DEFAULT_SHORTCUTS.items()
             if k not in {"capture_screen", "toggle_quick_panel"}}
    saved["capture_area"] = "Ctrl+Shift+D"
    saved["toggle_panel"] = "Ctrl+Shift+Q"
    upgraded = complete_shortcuts(saved)
    assert all(upgraded[k] == v for k, v in saved.items())
    assert set(upgraded) == set(DEFAULT_SHORTCUTS)
    assert len(set(shortcut_hooks(upgraded).values())) == len(upgraded)


def test_new_shortcut_emits_only_the_quick_panel_action(monkeypatch):
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
    events = []
    hotkeys.toggle_quick_panel.connect(lambda: events.append("quick"))
    hotkeys.toggle_panel.connect(lambda: events.append("full"))
    hotkeys.start()
    callbacks[shortcut_hooks(DEFAULT_SHORTCUTS)["toggle_quick_panel"]]()
    assert events == ["quick"]
    hotkeys.stop()
