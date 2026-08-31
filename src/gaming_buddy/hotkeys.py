from __future__ import annotations

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

SHORTCUT_LABELS = {
    "toggle_panel": "Show or hide panel",
    "quick_finder": "Find a saved card",
    "capture_area": "Capture screen area",
    "toggle_click_through": "Toggle click-through pins",
}

DEFAULT_SHORTCUTS = {
    "toggle_panel": "Ctrl+Shift+G",
    "quick_finder": "Ctrl+Shift+F",
    "capture_area": "Ctrl+Shift+S",
    "toggle_click_through": "Ctrl+Shift+L",
}

_MODIFIERS = {
    "ctrl": ("Ctrl", "<ctrl>"),
    "control": ("Ctrl", "<ctrl>"),
    "alt": ("Alt", "<alt>"),
    "shift": ("Shift", "<shift>"),
    "meta": ("Meta", "<cmd>"),
    "win": ("Meta", "<cmd>"),
}

_NAMED_KEYS = {
    "space": ("Space", "<space>"),
    "tab": ("Tab", "<tab>"),
    "backtab": ("Tab", "<tab>"),
    "esc": ("Esc", "<esc>"),
    "escape": ("Esc", "<esc>"),
    "return": ("Enter", "<enter>"),
    "enter": ("Enter", "<enter>"),
    "backspace": ("Backspace", "<backspace>"),
    "delete": ("Delete", "<delete>"),
    "del": ("Delete", "<delete>"),
    "insert": ("Insert", "<insert>"),
    "ins": ("Insert", "<insert>"),
    "home": ("Home", "<home>"),
    "end": ("End", "<end>"),
    "left": ("Left", "<left>"),
    "right": ("Right", "<right>"),
    "up": ("Up", "<up>"),
    "down": ("Down", "<down>"),
    "pgup": ("Page Up", "<page_up>"),
    "page up": ("Page Up", "<page_up>"),
    "pageup": ("Page Up", "<page_up>"),
    "pgdown": ("Page Down", "<page_down>"),
    "page down": ("Page Down", "<page_down>"),
    "pagedown": ("Page Down", "<page_down>"),
}


def parse_shortcut(value: str) -> tuple[str, str]:
    """Return a stable display name and pynput representation for a shortcut."""
    value = value.strip()
    if not value:
        raise ValueError("Every action needs a shortcut.")
    if "," in value:
        raise ValueError("Shortcut sequences are not supported; use one key combination.")

    parts = [part.strip() for part in value.split("+") if part.strip()]
    modifiers: dict[str, tuple[str, str]] = {}
    primary: tuple[str, str] | None = None
    for part in parts:
        lowered = part.casefold()
        if lowered in _MODIFIERS:
            display, hook = _MODIFIERS[lowered]
            modifiers[display] = (display, hook)
            continue
        if primary is not None:
            raise ValueError("Use exactly one non-modifier key in each shortcut.")
        if len(part) == 1 and part.isalnum():
            primary = (part.upper(), part.lower())
        elif lowered.startswith("f") and lowered[1:].isdigit():
            number = int(lowered[1:])
            if not 1 <= number <= 24:
                raise ValueError("Function keys must be between F1 and F24.")
            primary = (f"F{number}", f"<f{number}>")
        elif lowered in _NAMED_KEYS:
            primary = _NAMED_KEYS[lowered]
        else:
            raise ValueError(f"Unsupported shortcut key: {part}")

    if not modifiers:
        raise ValueError("Include Ctrl, Alt, Shift, or Meta in every shortcut.")
    if primary is None:
        raise ValueError("Add a non-modifier key to every shortcut.")

    ordered = [name for name in ("Ctrl", "Alt", "Shift", "Meta") if name in modifiers]
    display = "+".join([*ordered, primary[0]])
    hook = "+".join([*(modifiers[name][1] for name in ordered), primary[1]])
    return display, hook


def validate_shortcuts(shortcuts: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    used: dict[str, str] = {}
    for action, label in SHORTCUT_LABELS.items():
        if action not in shortcuts:
            raise ValueError(f"Missing shortcut for {label.lower()}.")
        display, hook = parse_shortcut(shortcuts[action])
        if hook in used:
            raise ValueError(f"{display} is already assigned to {used[hook].lower()}.")
        normalized[action] = display
        used[hook] = label
    return normalized


def shortcut_hooks(shortcuts: dict[str, str]) -> dict[str, str]:
    normalized = validate_shortcuts(shortcuts)
    return {action: parse_shortcut(value)[1] for action, value in normalized.items()}


class GlobalHotkeys(QObject):
    toggle_panel = Signal()
    quick_finder = Signal()
    capture_area = Signal()
    toggle_click_through = Signal()
    failed = Signal(str)

    def __init__(self, shortcuts: dict[str, str] | None = None) -> None:
        super().__init__()
        self._listener: keyboard.GlobalHotKeys | None = None
        self._shortcuts = validate_shortcuts(shortcuts or DEFAULT_SHORTCUTS)

    def start(self) -> None:
        try:
            hooks = shortcut_hooks(self._shortcuts)
            self._listener = keyboard.GlobalHotKeys(
                {
                    hooks["toggle_panel"]: self.toggle_panel.emit,
                    hooks["quick_finder"]: self.quick_finder.emit,
                    hooks["capture_area"]: self.capture_area.emit,
                    hooks["toggle_click_through"]: self.toggle_click_through.emit,
                }
            )
            self._listener.start()
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - platform hook errors vary
            self.failed.emit(str(exc))

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def update_shortcuts(self, shortcuts: dict[str, str]) -> None:
        self._shortcuts = validate_shortcuts(shortcuts)
        self.stop()
        self.start()
