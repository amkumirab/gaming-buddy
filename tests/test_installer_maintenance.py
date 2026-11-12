import base64
import os
import subprocess
import time
from pathlib import Path

import pytest

from gaming_buddy.hint_cards import HintContent
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Real Windows installer contract")


@pytest.fixture
def installer(tmp_path):
    import importlib.util

    helper = Path(__file__).parent / "helpers/installer_fixture.py"
    spec = importlib.util.spec_from_file_location("installer_fixture", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    compiler = module.compiler_path()
    if compiler is None:
        pytest.skip("Inno Setup 6 compiler is required for native installer tests")
    fixture = module.InstallerFixture(tmp_path, compiler)
    try:
        yield fixture
    finally:
        fixture.cleanup()


def install(fixture, version):
    result = fixture.run(fixture.setup(version))
    assert result.returncode == 0, (fixture.root / "last-setup.log").read_text(errors="replace")


def snapshot(directory):
    return {str(file.relative_to(directory)): file.read_bytes()
            for file in directory.rglob("*") if file.is_file()}


def test_install_upgrade_reinstall_and_uninstall_retain_real_cards(installer):
    import winreg

    install(installer, "0.0.9")
    assert "Maintenance operation: Install" in (installer.root / "last-setup.log").read_text()
    installer.data.mkdir()
    image = installer.data / "capture.png"
    image.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV1cAAAAASUVORK5CYII="
    ))
    with CardStore(installer.data / "cards.sqlite3") as store:
        store.add(Card(None, CardKind.NOTE, "Game", "Multiline", content="First\n\nLast\n",
                        tags=("route",), favorite=True, pinned=True, locked=True, collapsed=True,
                        x=120, y=150, width=480, height=300, opacity=0.65))
        store.add(Card(None, CardKind.NOTE, "Game", "Checklist", content="- [x] Map\n- [ ] Potion"))
        store.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=HintContent(("a", "b", "c"), 2)))
        store.add(Card(None, CardKind.IMAGE, "Game", "Map", image_path=str(image)))
    (installer.data / "settings.ini").write_text("[shortcuts]\nkey=Ctrl+Alt+K\n")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, installer.settings_key) as key:
        winreg.SetValueEx(key, "Shortcut", 0, winreg.REG_SZ, "Ctrl+Alt+K")
    before = snapshot(installer.data)
    obsolete = installer.install / "_internal/obsolete.txt"
    obsolete.write_text("old runtime")
    install(installer, "0.1.0")
    assert "Maintenance operation: Upgrade" in (installer.root / "last-setup.log").read_text()
    assert not obsolete.exists()
    assert snapshot(installer.data) == before
    install(installer, "0.1.0")
    assert "Maintenance operation: Reinstall" in (installer.root / "last-setup.log").read_text()
    assert snapshot(installer.data) == before
    with CardStore(installer.data / "cards.sqlite3") as store:
        assert len(store.list()) == 4
        assert next(card for card in store.list() if card.hints).hints.revealed == 2
    installer.uninstall()
    assert not (installer.install / "GamingBuddy.exe").exists()
    assert snapshot(installer.data) == before
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.settings_key) as key:
        assert winreg.QueryValueEx(key, "Shortcut")[0] == "Ctrl+Alt+K"


@pytest.mark.parametrize("newer,older", [("0.1.0", "0.0.9"), ("1.10.0", "1.9.0")])
def test_downgrade_is_numeric_and_leaves_every_program_file_unchanged(installer, newer, older):
    install(installer, newer)
    before = snapshot(installer.install)
    result = installer.run(installer.setup(older))
    assert result.returncode != 0
    assert "newer Gaming Buddy version" in (installer.root / "last-setup.log").read_text()
    assert snapshot(installer.install) == before


@pytest.mark.parametrize("metadata", ["9.0.0", "invalid", "1.2.3.4.5"])
def test_registry_metadata_cannot_bypass_downgrade_guard(installer, metadata):
    import winreg

    install(installer, "0.1.0")
    before = snapshot(installer.install)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.key, 0,
                        winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, metadata)
    assert installer.run(installer.setup("0.1.0")).returncode != 0
    assert snapshot(installer.install) == before


def test_running_fixture_app_blocks_install_and_uninstall_until_closed(installer):
    install(installer, "0.1.0")
    executable = installer.install / "GamingBuddy.exe"
    ready, stop = installer.root / "ready", installer.root / "stop"
    process = subprocess.Popen([str(executable), str(ready), str(stop)])
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        before = snapshot(installer.install)
        assert installer.run(installer.setup("0.2.0")).returncode != 0
        assert "tray menu" in (installer.root / "last-setup.log").read_text()
        assert installer.run(installer.install / "unins000.exe").returncode != 0
        assert "tray menu" in (installer.root / "last-setup.log").read_text()
        assert snapshot(installer.install) == before
    finally:
        stop.touch()
        process.wait(timeout=10)
    install(installer, "0.2.0")


def test_executable_version_wins_over_stale_registration(installer):
    import winreg

    install(installer, "0.2.0")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, installer.key, 0,
                        winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "0.0.1")
    before = snapshot(installer.install)
    assert installer.run(installer.setup("0.1.0")).returncode != 0
    assert snapshot(installer.install) == before


def test_newer_registration_in_other_registry_view_is_not_ignored(installer):
    import winreg

    install(installer, "0.1.0")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, installer.key, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_32KEY) as key:
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "0.3.0")
    before = snapshot(installer.install)
    assert installer.run(installer.setup("0.2.0")).returncode != 0
    assert snapshot(installer.install) == before


def test_locked_legacy_runtime_is_rejected_before_stale_files_are_deleted(installer):
    import ctypes
    from ctypes import wintypes

    install(installer, "0.1.0")
    before = snapshot(installer.install)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(installer.install / "_internal/runtime.txt"), 0x80000000,
                                1, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        assert installer.run(installer.setup("0.2.0")).returncode != 0
        assert "in use or cannot be updated" in (installer.root / "last-setup.log").read_text()
        assert snapshot(installer.install) == before
    finally:
        kernel.CloseHandle(handle)
    install(installer, "0.2.0")
