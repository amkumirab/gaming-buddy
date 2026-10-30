from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_installer_lifecycle_has_a_fresh_runner_and_publication_requires_it():
    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    build, rest = workflow.split("  installer_test:\n", maxsplit=1)
    installer, publish = rest.split("  publish:\n", maxsplit=1)

    assert "Test installer lifecycle" not in build
    assert "runs-on: windows-2025" in installer
    assert "needs: build" in installer
    assert "actions/download-artifact@" in installer
    assert "gaming-buddy-windows-${{ github.run_id }}" in installer
    assert "./scripts/test_windows_installer.ps1" in installer
    assert "python -m pytest" not in installer
    assert "needs: [build, installer_test]" in publish
    assert "startsWith(github.ref, 'refs/tags/v')" in publish


def test_lifecycle_keeps_its_personal_workspace_refusal_guards():
    script = (ROOT / "scripts/test_windows_installer.ps1").read_text(encoding="utf-8")
    assert '$env:GITHUB_ACTIONS -ne "true"' in script
    assert '$env:RUNNER_ENVIRONMENT -ne "github-hosted"' in script
    assert 'throw "Refusing to overwrite existing application state: $path"' in script
