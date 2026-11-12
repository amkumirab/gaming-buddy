"""Cooperate with Inno Setup without changing the single-instance protocol."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

APP_MUTEX = r"Local\GamingBuddy.App.57C1EB82-EEAD-4E5F-8F24-49C61A578D08"
SETUP_MUTEX = r"Local\GamingBuddy.Setup.57C1EB82-EEAD-4E5F-8F24-49C61A578D08"
_process_handles: dict[str, int] = {}


class InstallerBusyError(RuntimeError):
    pass


def _setup_running(kernel, name: str) -> bool:
    setup = kernel.OpenMutexW(0x100000, False, name)
    if setup:
        kernel.CloseHandle(setup)
        return True
    if ctypes.get_last_error() != 2:  # ERROR_FILE_NOT_FOUND
        raise InstallerBusyError("Could not check installation status. Restart Windows and retry.")
    return False


def hold_installer_guard(app_name: str = APP_MUTEX, setup_name: str = SETUP_MUTEX,
                         *, wait_seconds: float = 0) -> None:
    if os.name != "nt":
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    deadline = time.monotonic() + wait_seconds
    # The installer may explicitly launch the app before releasing its own mutex.
    while wait_seconds > 0 and _setup_running(kernel, setup_name):
        if time.monotonic() >= deadline:
            raise InstallerBusyError("The Gaming Buddy installer is running. Finish or cancel it "
                                     "before opening the application.")
        time.sleep(0.05)
    # Advertise startup before checking Setup, closing the launch/install race.
    handle = kernel.CreateMutexW(None, False, app_name)
    if not handle:
        raise InstallerBusyError("Could not check installation status. Restart Windows and retry.")
    try:
        if _setup_running(kernel, setup_name):
            raise InstallerBusyError("The Gaming Buddy installer is running. Finish or cancel it "
                                     "before opening the application.")
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    if app_name in _process_handles:
        kernel.CloseHandle(handle)
    else:
        # Deliberately let Windows release this at process termination, after Qt/DLL teardown.
        _process_handles[app_name] = handle
