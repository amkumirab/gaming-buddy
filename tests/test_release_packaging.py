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


def test_installer_is_per_user_and_preserves_workspace() -> None:
    installer = (PROJECT_ROOT / "packaging/gaming-buddy.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in installer
    assert "MinVersion=10.0.17763" in installer
    assert r"DefaultDirName={localappdata}\Programs\Gaming Buddy" in installer
    assert "recursesubdirs createallsubdirs" in installer
    assert "[UninstallDelete]" not in installer
    assert r"{localappdata}\GamingBuddy" not in installer


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
