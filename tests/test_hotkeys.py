import pytest

from gaming_buddy.hotkeys import (
    DEFAULT_SHORTCUTS,
    parse_shortcut,
    shortcut_hooks,
    validate_shortcuts,
)


def test_default_shortcuts_are_valid():
    assert validate_shortcuts(DEFAULT_SHORTCUTS) == DEFAULT_SHORTCUTS
    assert shortcut_hooks(DEFAULT_SHORTCUTS) == {
        "toggle_panel": "<ctrl>+<shift>+g",
        "capture_area": "<ctrl>+<shift>+s",
        "toggle_click_through": "<ctrl>+<shift>+l",
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
