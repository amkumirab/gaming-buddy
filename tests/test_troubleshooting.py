import pytest
from PySide6.QtWidgets import QApplication

from gaming_buddy.diagnostics import DiagnosticCheck, DiagnosticReport
from gaming_buddy.troubleshooting import TroubleshootingPanel


@pytest.fixture(scope="module")
def application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_report_is_previewed_and_copied_only_on_request(
    application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports = [
        DiagnosticReport(
            ("App version: 0.1.0",),
            (DiagnosticCheck("Storage", "Needs attention", "Check disk space."),),
        ),
        DiagnosticReport(
            ("App version: 0.1.0",), (DiagnosticCheck("Storage", "Ready", "Write succeeded."),)
        ),
    ]
    calls: list[int] = []
    copies: list[str] = []

    class Clipboard:
        def setText(self, text: str) -> None:
            copies.append(text)

    monkeypatch.setattr(QApplication, "clipboard", lambda: Clipboard())

    def provider() -> DiagnosticReport:
        report = reports[len(calls)]
        calls.append(1)
        return report

    panel = TroubleshootingPanel(provider)
    try:
        assert not panel.copy_button.isEnabled()
        assert calls == copies == []
        panel.run_button.click()
        assert panel.report_view.toPlainText() == reports[0].as_text()
        assert "1 item(s)" in panel.status.text()
        assert copies == []
        panel.copy_button.click()
        assert copies == [reports[0].as_text()]
        panel.run_button.click()
        assert panel.report_view.toPlainText() == reports[1].as_text()
        assert "Needs attention" not in panel.report_view.toPlainText()
        assert copies == [reports[0].as_text()]
    finally:
        panel.close()


def test_provider_failure_does_not_reveal_exception_content(application: QApplication) -> None:
    def provider() -> DiagnosticReport:
        raise RuntimeError("private-note-text; C:\\Users\\private-account\\secret.png")

    panel = TroubleshootingPanel(provider)
    try:
        panel.run_checks()
        assert "Restart the app" in panel.report_view.toPlainText()
        assert "private" not in panel.report_view.toPlainText()
    finally:
        panel.close()
