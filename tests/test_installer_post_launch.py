import ctypes
import os
import subprocess
import sys
import time
import uuid
from ctypes import wintypes
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows post-install launch handoff")
@pytest.mark.parametrize("entry", ["guard", "application"])
def test_post_install_launch_waits_without_opening_app_until_setup_finishes(entry):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token = uuid.uuid4().hex
    app_name, setup_name = f"Local\\GBPost.App.{token}", f"Local\\GBPost.Setup.{token}"
    setup = kernel.CreateMutexW(None, False, setup_name)
    assert setup
    code = ("import sys; from gaming_buddy.installer_guard import hold_installer_guard; "
            "print('BOOT', flush=True); "
            "hold_installer_guard(sys.argv[1], sys.argv[2], wait_seconds=3); "
            "print('HELD', flush=True)")
    command = [sys.executable, "-u", "-c", code, app_name, setup_name]
    expected = "HELD"
    if entry == "application":
        script = Path(__file__).parent / "helpers/installer_startup.py"
        command = [sys.executable, "-u", str(script), app_name, setup_name, "--after-install"]
        expected = "WORKSPACE_ALLOWED"
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "BOOT"
        time.sleep(0.15)
        assert process.poll() is None
        kernel.CloseHandle(setup)
        setup = None
        output, error = process.communicate(timeout=10)
        assert process.returncode == 0, error
        assert expected in output
    finally:
        if setup:
            kernel.CloseHandle(setup)
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
