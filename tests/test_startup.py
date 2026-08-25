from __future__ import annotations

from pathlib import Path
from typing import Self

from gaming_buddy.startup import RUN_KEY, VALUE_NAME, StartupManager, build_startup_command


class FakeKey:
    def __init__(self, registry: FakeRegistry) -> None:
        self.registry = registry

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeRegistry:
    HKEY_CURRENT_USER = object()
    KEY_QUERY_VALUE = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def OpenKey(self, _root: object, path: str, *_: object) -> FakeKey:
        assert path == RUN_KEY
        if VALUE_NAME not in self.values:
            raise FileNotFoundError
        return FakeKey(self)

    def CreateKeyEx(self, _root: object, path: str, *_: object) -> FakeKey:
        assert path == RUN_KEY
        return FakeKey(self)

    def QueryValueEx(self, key: FakeKey, name: str) -> tuple[str, int]:
        return key.registry.values[name], self.REG_SZ

    def SetValueEx(
        self,
        key: FakeKey,
        name: str,
        _reserved: int,
        _kind: int,
        value: str,
    ) -> None:
        key.registry.values[name] = value

    def DeleteValue(self, key: FakeKey, name: str) -> None:
        del key.registry.values[name]


def test_frozen_startup_command_quotes_executable() -> None:
    command = build_startup_command(
        Path(r"C:\Users\Player One\AppData\Gaming Buddy\GamingBuddy.exe"),
        frozen=True,
    )

    assert command == r'"C:\Users\Player One\AppData\Gaming Buddy\GamingBuddy.exe"'


def test_source_startup_command_runs_package_module() -> None:
    command = build_startup_command(Path(r"C:\Python\python.exe"), frozen=False)

    assert command == r"C:\Python\python.exe -m gaming_buddy"


def test_startup_manager_enables_and_disables_current_command() -> None:
    registry = FakeRegistry()
    manager = StartupManager('"C:\\Gaming Buddy\\GamingBuddy.exe"', registry=registry)

    assert manager.is_enabled() is False
    manager.set_enabled(True)
    assert manager.is_enabled() is True
    assert registry.values[VALUE_NAME] == manager.command

    manager.set_enabled(False)
    assert manager.is_enabled() is False


def test_startup_manager_replaces_outdated_command() -> None:
    registry = FakeRegistry()
    registry.values[VALUE_NAME] = '"C:\\Old Location\\GamingBuddy.exe"'
    manager = StartupManager('"C:\\New Location\\GamingBuddy.exe"', registry=registry)

    assert manager.is_enabled() is False
    manager.set_enabled(True)
    assert registry.values[VALUE_NAME] == manager.command
