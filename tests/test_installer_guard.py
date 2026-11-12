import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from gaming_buddy.installer_guard import (
    APP_MUTEX,
    SETUP_MUTEX,
    InstallerBusyError,
    hold_installer_guard,
)


def test_python_and_installer_mutex_names_match():
    script = (Path(__file__).parents[1] / "packaging/gaming-buddy.iss").read_text()
    for constant, expected in (("MyAppMutex", APP_MUTEX), ("MySetupMutex", SETUP_MUTEX)):
        assert re.search(rf'#define {constant} "([^"]+)"', script).group(1) == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex contract")
def test_app_mutex_lives_until_process_exit_and_setup_blocks_new_start():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenMutexW.restype = wintypes.HANDLE
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token = uuid.uuid4().hex
    app_name, setup_name = f"Local\\GBTest.App.{token}", f"Local\\GBTest.Setup.{token}"
    code = ("import sys; from gaming_buddy.installer_guard import hold_installer_guard; "
            "hold_installer_guard(sys.argv[1], sys.argv[2]); print('READY', flush=True); input()")
    process = subprocess.Popen([sys.executable, "-u", "-c", code, app_name, setup_name],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "READY"
        handle = kernel.OpenMutexW(0x100000, False, app_name)
        assert handle
        kernel.CloseHandle(handle)
        process.communicate("\n", timeout=10)
        assert process.returncode == 0
        assert not kernel.OpenMutexW(0x100000, False, app_name)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    setup = kernel.CreateMutexW(None, False, setup_name)
    assert setup
    try:
        with pytest.raises(InstallerBusyError, match="installer"):
            hold_installer_guard(app_name, setup_name)
        with pytest.raises(InstallerBusyError, match="installer"):
            hold_installer_guard(app_name, setup_name, wait_seconds=0.02)
        assert not kernel.OpenMutexW(0x100000, False, app_name)
        script = Path(__file__).parent / "helpers/installer_startup.py"
        result = subprocess.run([sys.executable, "-X", "faulthandler", str(script),
                                 app_name, setup_name], capture_output=True, text=True,
                                check=False, timeout=15)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "installer is running" in result.stdout
        assert "AssertionError" not in result.stderr
    finally:
        kernel.CloseHandle(setup)
