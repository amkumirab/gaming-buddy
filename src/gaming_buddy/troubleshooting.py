from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.diagnostics import DiagnosticCheck, DiagnosticReport


class TroubleshootingPanel(QWidget):
    def __init__(
        self,
        provider: Callable[[], DiagnosticReport],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("troubleshootingPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._provider = provider
        self._report: DiagnosticReport | None = None
        layout = QVBoxLayout(self)
        introduction = QLabel(
            "Check local storage, the tray icon, and global shortcuts. "
            "The checks use temporary files and do not read your saved cards."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        privacy = QLabel(
            "The report excludes personal content and file paths. Nothing is uploaded. "
            "Copying the report replaces the clipboard only when you choose to do so."
        )
        privacy.setObjectName("muted")
        privacy.setWordWrap(True)
        layout.addWidget(privacy)

        actions = QHBoxLayout()
        self.run_button = QPushButton("Run checks")
        self.run_button.setObjectName("primary")
        self.run_button.setAccessibleName("Run troubleshooting checks")
        self.run_button.setToolTip("Check local write access and runtime status")
        self.run_button.setAutoDefault(True)
        self.run_button.clicked.connect(self.run_checks)
        self.copy_button = QPushButton("Copy diagnostic report")
        self.copy_button.setAccessibleName("Copy diagnostic report")
        self.copy_button.setToolTip("Copy the report below to share with support")
        self.copy_button.setAutoDefault(True)
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_report)
        actions.addWidget(self.run_button)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.status = QLabel("No checks have been run. Choose Run checks to begin.")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Troubleshooting status")
        layout.addWidget(self.status)
        self.report_view = QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setTabChangesFocus(True)
        self.report_view.setAccessibleName("Diagnostic report preview")
        self.report_view.setPlaceholderText("Your report will appear here before you copy it.")
        layout.addWidget(self.report_view, 1)
        self.setTabOrder(self.run_button, self.copy_button)
        self.setTabOrder(self.copy_button, self.report_view)

    def run_checks(self) -> None:
        try:
            self._report = self._provider()
        except Exception:  # noqa: BLE001 - keep unexpected exception content out of reports
            self._report = DiagnosticReport(
                environment=(),
                checks=(
                    DiagnosticCheck(
                        "Diagnostics",
                        "Needs attention",
                        "Checks could not finish. Restart the app and try again.",
                    ),
                ),
            )
        self.report_view.setPlainText(self._report.as_text())
        self.copy_button.setEnabled(True)
        warnings = sum(check.status == "Needs attention" for check in self._report.checks)
        if warnings:
            self.status.setText(
                f"Checks complete: {warnings} item(s) need attention. See the suggestions below."
            )
        else:
            self.status.setText(
                "Checks complete. Review the report for any paused or unknown status."
            )

    def copy_report(self) -> None:
        if self._report is None:
            return
        QApplication.clipboard().setText(self._report.as_text())
        self.status.setText("Diagnostic report copied. Review it before sharing with support.")
