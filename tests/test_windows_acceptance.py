from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/prepare_windows_acceptance.ps1"
COMMIT = "14f296833373c96c0a01f3dc060f09bee6e93f89"
RUN_URL = "https://github.com/amkumirab/gaming-buddy/actions/runs/41031956975"


def candidate(directory: Path, version: str = "0.1.0") -> Path:
    directory.mkdir()
    installer = directory / f"Gaming-Buddy-Setup-{version}-x64.exe"
    installer.write_bytes(b"synthetic installer fixture, never executed")
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    Path(f"{installer}.sha256").write_text(f"{digest}  {installer.name}\n", encoding="ascii")
    return installer


def prepare(installer, output, *, commit=COMMIT, url=RUN_URL):
    # A Python child of pwsh inherits PS7 module paths. Let Windows PowerShell
    # reconstruct its own default module paths instead of importing PS7 assemblies.
    environment = {key: value for key, value in os.environ.items() if key.casefold() != "psmodulepath"}
    return subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
            "-InstallerPath", str(installer), "-BuildCommit", commit,
            "-BuildRunUrl", url, "-ReportDirectory", str(output),
        ],
        capture_output=True, text=True, timeout=30, check=False, env=environment,
    )


@pytest.mark.parametrize("version", ["0.1.0", "1.12.3"])
def test_prepare_verified_candidate_without_approving_desktop_tests(tmp_path, version):
    installer = candidate(tmp_path / "download with spaces", version)
    output = tmp_path / "report with spaces"
    result = prepare(installer, output)

    assert result.returncode == 0, result.stderr
    identity = json.loads((output / "candidate.json").read_text(encoding="utf-8-sig"))
    assert identity["commit"] == COMMIT
    assert identity["build_run_url"] == RUN_URL
    assert identity["version"] == version
    assert identity["installer"] == installer.name
    assert identity["sha256"] == hashlib.sha256(installer.read_bytes()).hexdigest()
    assert identity["checksum"] == "passed"
    assert identity["clean_machine_acceptance"] == "not_tested"
    assert identity["publication"] == "pending"
    report = (output / "acceptance.md").read_text(encoding="utf-8-sig")
    assert COMMIT in report and installer.name in report and RUN_URL in report
    assert "Python and developer tools absent before installation: Not verified" in report
    assert "| Install as standard user without Python | Not tested |" in report
    assert "this template does not approve publication" in report
    assert f"/blob/{COMMIT}/docs/windows-release.md#" in report
    assert (output / "game-compatibility.md").is_file()
    assert installer.read_bytes() == b"synthetic installer fixture, never executed"


@pytest.mark.parametrize("problem", ["corrupt", "checksum_name", "missing_checksum", "missing"])
def test_invalid_download_leaves_no_report(tmp_path, problem):
    installer = candidate(tmp_path / "download")
    checksum = Path(f"{installer}.sha256")
    if problem == "corrupt":
        installer.write_bytes(b"changed")
    elif problem == "checksum_name":
        checksum.write_text(checksum.read_text().replace(installer.name, "other.exe"))
    elif problem == "missing_checksum":
        checksum.unlink()
    else:
        installer.unlink()
    output = tmp_path / "report"

    result = prepare(installer, output)

    assert result.returncode != 0
    assert not output.exists()


def test_installer_filename_must_match_distribution_contract(tmp_path):
    original = candidate(tmp_path / "download")
    installer = original.with_name("GamingBuddy.exe")
    original.rename(installer)
    Path(f"{original}.sha256").rename(Path(f"{installer}.sha256"))
    output = tmp_path / "report"

    result = prepare(installer, output)

    assert result.returncode != 0
    assert "Expected Gaming-Buddy-Setup" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("commit,url", [
    ("14f2968", RUN_URL),
    (COMMIT, "https://github.com/another/repo/actions/runs/123"),
    (COMMIT, RUN_URL + "?untrusted=true"),
])
def test_invalid_build_identity_leaves_no_report(tmp_path, commit, url):
    installer = candidate(tmp_path / "download")
    output = tmp_path / "report"

    result = prepare(installer, output, commit=commit, url=url)

    assert result.returncode != 0
    assert not output.exists()


def test_existing_report_is_never_replaced(tmp_path):
    installer = candidate(tmp_path / "download")
    output = tmp_path / "report"
    first = prepare(installer, output)
    assert first.returncode == 0, first.stderr
    report = output / "acceptance.md"
    report.write_text("Tester evidence that must survive", encoding="utf-8")

    result = prepare(installer, output)

    assert result.returncode != 0
    assert report.read_text(encoding="utf-8") == "Tester evidence that must survive"
