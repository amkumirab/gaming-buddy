from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - the application targets Windows
    winreg = None  # type: ignore[assignment]


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "GamingBuddy"


class StartupError(RuntimeError):
    pass


def build_startup_command(
    executable: str | Path | None = None,
    *,
    frozen: bool | None = None,
) -> str:
    executable_path = Path(executable or sys.executable).resolve()
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    arguments = [str(executable_path)]
    if not is_frozen:
        arguments.extend(("-m", "gaming_buddy"))
    return subprocess.list2cmdline(arguments)


class StartupManager:
    def __init__(
        self,
        command: str | None = None,
        *,
        registry: Any = None,
    ) -> None:
        self.command = command or build_startup_command()
        self.registry = registry if registry is not None else winreg

    @property
    def supported(self) -> bool:
        return self.registry is not None

    def is_enabled(self) -> bool:
        if not self.supported:
            return False
        try:
            with self.registry.OpenKey(
                self.registry.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                self.registry.KEY_QUERY_VALUE,
            ) as key:
                value, _ = self.registry.QueryValueEx(key, VALUE_NAME)
        except OSError:
            return False
        return str(value) == self.command

    def set_enabled(self, enabled: bool) -> None:
        if not self.supported:
            raise StartupError("Launch at sign-in is available only on Windows.")
        try:
            if enabled:
                with self.registry.CreateKeyEx(
                    self.registry.HKEY_CURRENT_USER,
                    RUN_KEY,
                    0,
                    self.registry.KEY_SET_VALUE,
                ) as key:
                    self.registry.SetValueEx(
                        key,
                        VALUE_NAME,
                        0,
                        self.registry.REG_SZ,
                        self.command,
                    )
                return

            try:
                with self.registry.OpenKey(
                    self.registry.HKEY_CURRENT_USER,
                    RUN_KEY,
                    0,
                    self.registry.KEY_SET_VALUE,
                ) as key:
                    self.registry.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                return
        except OSError as error:
            action = "enable" if enabled else "disable"
            raise StartupError(f"Could not {action} launch at sign-in: {error}") from error
