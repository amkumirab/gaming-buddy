import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import gaming_buddy.dashboard as dashboard_module
import gaming_buddy.diagnostics as diagnostics_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.diagnostics import DiagnosticHistory, IssueKind, collect_diagnostics
from gaming_buddy.settings_dialog import SettingsDialog
from gaming_buddy.storage import CardStore


@pytest.fixture(scope="module")
def application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_checks_preserve_user_files_and_exclude_private_details(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures = tmp_path / "Private-player-name"
    captures.mkdir()
    note = tmp_path / "gaming-buddy.sqlite3"
    note.write_bytes(b"private-note-content")
    screenshot = captures / "secret-puzzle.png"
    screenshot.write_bytes(b"private-image-content")
    before = {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(diagnostics_module.QSystemTrayIcon, "isSystemTrayAvailable", lambda: True)
    report = collect_diagnostics(tmp_path, captures, shortcuts_running=True, tray_visible=True)

    assert all(check.status in {"Ready", "Running"} for check in report.checks)
    assert before == {
        str(path.relative_to(tmp_path)): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert not list(tmp_path.rglob(".gaming-buddy-check-*"))
    text = report.as_text()
    for private in (
        str(tmp_path),
        captures.name,
        screenshot.name,
        "private-note-content",
        "private-image-content",
    ):
        assert private not in text


def test_permission_errors_are_actionable_without_exception_text(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(**_kwargs: object) -> None:
        raise PermissionError("Sensitive account name and private file path")

    monkeypatch.setattr(diagnostics_module, "TemporaryDirectory", denied)
    report = collect_diagnostics(tmp_path, tmp_path)
    assert all(check.status == "Needs attention" for check in report.checks[:2])
    assert "Allow write access" in report.as_text()
    assert "Sensitive account" not in report.as_text()


def test_missing_capture_folder_and_paused_shortcuts_are_distinct(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics_module.QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    report = collect_diagnostics(
        tmp_path, tmp_path / "missing", shortcuts_running=True, shortcuts_paused=True
    )
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["Notes folder (SQLite)"] == "Ready"
    assert statuses["Screenshot folder (PNG)"] == "Needs attention"
    assert statuses["System tray"] == "Needs attention"
    assert statuses["Global shortcuts"] == "Paused in Settings"
    assert "before Settings opened" in report.as_text()


def test_history_accepts_only_fixed_categories_and_keeps_last_five() -> None:
    history = DiagnosticHistory()
    with pytest.raises(TypeError, match="known diagnostic category"):
        history.record("private exception text")  # type: ignore[arg-type]
    history.record(IssueKind.SHORTCUTS)
    for _ in range(5):
        history.record(IssueKind.CAPTURE)
    assert len(history.snapshot()) == 5
    assert all(issue.kind is IssueKind.CAPTURE for issue in history.snapshot())


@pytest.mark.parametrize("running,status", [(None, "Unknown"), (False, "Needs attention")])
def test_unavailable_listener_is_not_reported_as_a_settings_pause(
    application: QApplication,
    tmp_path: Path,
    running: bool | None,
    status: str,
) -> None:
    report = collect_diagnostics(
        tmp_path, tmp_path, shortcuts_running=running, shortcuts_paused=True
    )
    assert report.checks[-1].status == status


def test_png_encoder_failure_cleans_up_temporary_files(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics_module.QImage, "save", lambda *_args: False)
    report = collect_diagnostics(tmp_path, tmp_path)
    assert report.checks[0].status == "Ready"
    assert report.checks[1].status == "Needs attention"
    assert "PNG encoding failed" in report.as_text()
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def dashboard(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Dashboard]:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_args: settings)
    captures = tmp_path / "captures"
    captures.mkdir()
    store = CardStore(tmp_path / "gaming-buddy.sqlite3")
    panel = Dashboard(store, captures)
    application.processEvents()
    try:
        yield panel
    finally:
        panel.note_draft_timer.stop()
        panel.game_detector.stop()
        panel.tray.hide()
        panel._really_quit = True
        panel.close()
        store.close()


@pytest.mark.parametrize("action", ["save_note", "pin_note"])
def test_failed_note_save_preserves_text_and_records_only_a_category(
    dashboard: Dashboard,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    def fail(_card: object) -> None:
        raise sqlite3.OperationalError("Private-account path and sensitive note")

    monkeypatch.setattr(dashboard.store, "add", fail)
    warnings: list[str] = []
    monkeypatch.setattr(
        dashboard_module.QMessageBox, "warning", lambda _p, _t, text: warnings.append(text)
    )
    note = "Private multiline note\nKeep all of this text."
    dashboard.note_input.setPlainText(note)
    getattr(dashboard, action)()
    assert dashboard.note_input.toPlainText() == note
    assert dashboard.pins == {}
    assert len(warnings) == 1
    assert "Private-account" not in warnings[0]
    assert dashboard.diagnostic_history.snapshot()[-1].kind is IssueKind.NOTE
    report = collect_diagnostics(
        dashboard.store.database.parent,
        dashboard.captures_dir,
        recent_issues=dashboard.diagnostic_history.snapshot(),
    ).as_text()
    assert "Note saving failed" in report
    assert note not in report
    assert "Private-account" not in report


def test_settings_capture_listener_state_before_pausing_and_resume_on_cancel(
    dashboard: Dashboard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"running": True}
    dashboard.shortcut_status = lambda: state["running"]
    dashboard.shortcut_editing_started.connect(lambda: state.update(running=False))
    dashboard.shortcut_editing_cancelled.connect(lambda: state.update(running=True))
    reports: list[str] = []

    def inspect(dialog: SettingsDialog) -> int:
        assert not state["running"]
        dialog.troubleshooting.run_checks()
        reports.append(dialog.troubleshooting.report_view.toPlainText())
        dialog.close()
        return 0

    monkeypatch.setattr(SettingsDialog, "exec", inspect)
    dashboard.open_settings()
    assert state["running"]
    assert "Global shortcuts: Paused in Settings" in reports[0]
    assert "Notes folder (SQLite): Ready" in reports[0]
    assert "Screenshot folder (PNG): Ready" in reports[0]


def test_capture_and_shortcut_failures_are_sanitized_and_cancellation_is_not_an_error(
    dashboard: Dashboard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dashboard_module.QMessageBox, "warning", lambda *_args: None)
    dashboard._on_update_download_failed("Update download cancelled.")
    assert dashboard.diagnostic_history.snapshot() == ()
    dashboard._capture_failed("Private-puzzle content and sensitive path")
    dashboard.on_shortcuts_failed("Private-account exception details")
    issues = dashboard.diagnostic_history.snapshot()
    assert [issue.kind for issue in issues] == [IssueKind.CAPTURE, IssueKind.SHORTCUTS]
    report = collect_diagnostics(
        dashboard.store.database.parent,
        dashboard.captures_dir,
        recent_issues=issues,
    ).as_text()
    assert "Private-" not in report
