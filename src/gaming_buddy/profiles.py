from __future__ import annotations

import ctypes
import json
import os
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import QObject, QSettings, QTimer, Signal


@dataclass(frozen=True, slots=True)
class ActiveApplication:
    executable: str
    title: str
    process_id: int


def normalize_executable(value: str) -> str:
    return Path(value.strip().replace("\\", "/")).name.casefold()


def belongs_to_profile(card_game: str, active_game: str) -> bool:
    card_game = (card_game.strip() or "General").casefold()
    return card_game in {active_game.strip().casefold(), "general"}


def read_foreground_application() -> ActiveApplication | None:
    if sys.platform != "win32":
        return None

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    foreground = user32.GetForegroundWindow()
    if not foreground:
        return None

    title_length = user32.GetWindowTextLengthW(foreground)
    title_buffer = ctypes.create_unicode_buffer(max(1, title_length + 1))
    user32.GetWindowTextW(foreground, title_buffer, len(title_buffer))

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(process_id))
    if not process_id.value:
        return None

    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(
        process_query_limited_information,
        False,
        process_id.value,
    )
    if not handle:
        return None
    try:
        path_buffer = ctypes.create_unicode_buffer(32768)
        path_size = wintypes.DWORD(len(path_buffer))
        if not kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            path_buffer,
            ctypes.byref(path_size),
        ):
            return None
        executable = normalize_executable(path_buffer.value)
        if not executable:
            return None
        return ActiveApplication(executable, title_buffer.value.strip(), int(process_id.value))
    finally:
        kernel32.CloseHandle(handle)


class GameProfileStore:
    settings_key = "profiles/executable_map"

    def __init__(self, settings: QSettings) -> None:
        self.settings = settings
        self._profiles = self._load()

    def all(self) -> dict[str, str]:
        return self._profiles.copy()

    def game_for(self, executable: str) -> str | None:
        return self._profiles.get(normalize_executable(executable))

    def link(self, executable: str, game: str) -> None:
        executable = normalize_executable(executable)
        game = game.strip()
        if not executable:
            raise ValueError("An executable name is required.")
        if not game:
            raise ValueError("A game profile name is required.")
        self._profiles[executable] = game
        self._save()

    def replace(self, profiles: dict[str, str]) -> None:
        cleaned: dict[str, str] = {}
        for executable, game in profiles.items():
            executable = normalize_executable(executable)
            game = game.strip()
            if executable and game:
                cleaned[executable] = game
        self._profiles = cleaned
        self._save()

    def _load(self) -> dict[str, str]:
        raw = self.settings.value(self.settings_key, "{}")
        try:
            values = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        if not isinstance(values, dict):
            return {}
        return {
            executable: game.strip()
            for key, value in values.items()
            if (executable := normalize_executable(str(key))) and (game := str(value).strip())
        }

    def _save(self) -> None:
        self.settings.setValue(
            self.settings_key,
            json.dumps(self._profiles, ensure_ascii=False, sort_keys=True),
        )
        self.settings.sync()


class ActiveGameDetector(QObject):
    active_changed = Signal(object)

    ignored_executables: ClassVar[set[str]] = {
        "applicationframehost.exe",
        "explorer.exe",
        "searchhost.exe",
        "shellexperiencehost.exe",
        "startmenuexperiencehost.exe",
    }

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        reader: Callable[[], ActiveApplication | None] = read_foreground_application,
        own_process_id: int | None = None,
        interval_ms: int = 1200,
    ) -> None:
        super().__init__(parent)
        self._reader = reader
        self._own_process_id = own_process_id if own_process_id is not None else os.getpid()
        self._last_external: ActiveApplication | None = None
        self._last_identity: tuple[str, int] | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll_now)

    @property
    def last_external_application(self) -> ActiveApplication | None:
        return self._last_external

    def start(self) -> None:
        self.poll_now()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def poll_now(self) -> None:
        try:
            application = self._reader()
        except OSError:
            return
        if application is None:
            return
        executable = normalize_executable(application.executable)
        if application.process_id == self._own_process_id or executable in self.ignored_executables:
            return
        application = ActiveApplication(executable, application.title, application.process_id)
        self._last_external = application
        identity = (application.executable, application.process_id)
        if identity == self._last_identity:
            return
        self._last_identity = identity
        self.active_changed.emit(application)
