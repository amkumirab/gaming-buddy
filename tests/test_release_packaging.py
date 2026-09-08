from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_metadata_is_synchronized() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_release.py", "--tag", "v0.1.0"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "version 0.1.0" in result.stdout


def test_release_metadata_rejects_mismatched_tag() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_release.py", "--tag", "v9.9.9"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert "does not match project version" in result.stderr


def test_installer_is_per_user_and_preserves_workspace_by_default() -> None:
    installer = (PROJECT_ROOT / "packaging/gaming-buddy.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in installer
    assert "MinVersion=10.0.17763" in installer
    assert r"DefaultDirName={localappdata}\Programs\Gaming Buddy" in installer
    assert "recursesubdirs createallsubdirs" in installer
    assert "ValueName: \"GamingBuddy\"; Flags: uninsdeletevalue dontcreatekey noerror" in installer
    assert "[UninstallDelete]" not in installer
    assert "if (not RemoveData) and (not UninstallSilent) then" in installer
    assert "MB_YESNO or MB_DEFBUTTON2" in installer
    assert "Choose No to keep them for a future installation." in installer
    assert "function HasCommandLineParameter" in installer
    assert "HasCommandLineParameter('/PURGEUSERDATA')" in installer
    assert r"DelTree(ExpandConstant('{localappdata}\GamingBuddy')" in installer
    assert r"RegDeleteKeyIncludingSubkeys(HKCU, 'Software\GamingBuddy')" in installer


def test_installer_supports_clean_updates_and_optional_launch() -> None:
    installer = (PROJECT_ROOT / "packaging/gaming-buddy.iss").read_text(encoding="utf-8")

    assert "UsePreviousAppDir=yes" in installer
    assert "UsePreviousTasks=yes" in installer
    assert '[InstallDelete]\nType: filesandordirs; Name: "{app}\\_internal"' in installer
    assert "postinstall skipifsilent unchecked" in installer
    assert "SetupLogging=yes" in installer


def test_installer_build_script_generates_a_sha256_file() -> None:
    script = (PROJECT_ROOT / "scripts/build_windows_installer.ps1").read_text(
        encoding="utf-8"
    )

    assert "scripts/validate_release.py" in script
    assert "Get-FileHash -LiteralPath $installer -Algorithm SHA256" in script
    assert '"$installer.sha256"' in script
    assert "Gaming-Buddy-Setup-$version-x64.exe" in script
    assert '"$env:LOCALAPPDATA\\Programs\\Inno Setup 6\\ISCC.exe"' in script


def test_release_workflow_uses_separate_write_permission() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/windows-release.yml").read_text(
        encoding="utf-8"
    )

    build_job, publish_job = workflow.split("  publish:\n", maxsplit=1)
    assert "contents: read" in build_job
    assert "contents: write" not in build_job
    assert "contents: write" in publish_job
    assert "--verify-tag" in publish_job
    assert "scripts/validate_release.py" in workflow
    assert "./scripts/build_windows_installer.ps1 -SkipApplicationBuild" in workflow


def test_windows_bundle_pins_compatible_qt_runtime_dependencies() -> None:
    specification = (PROJECT_ROOT / "packaging/gaming-buddy.spec").read_text(
        encoding="utf-8"
    )

    assert '"VCRUNTIME140.dll"' in specification
    assert '"MSVCP140.dll"' in specification
    assert '"icuuc.dll", "icudt78.dll"' in specification
    assert "console=False" in specification
