"""Run the real app against disposable data and quit through its normal action."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer

import gaming_buddy.app as app_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.paths import ensure_data_dirs

root = Path(sys.argv[1])
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
    QSettings.setPath(QSettings.Format.IniFormat, scope, str(root / "settings"))
settings = QSettings("GamingBuddy", "GamingBuddy")
settings.setValue("onboarding/completed", True)
settings.setValue("updates/automatic_checks", False)
settings.sync()
app_module.ensure_data_dirs = lambda: ensure_data_dirs(root / "data")


class ObservedDashboard(Dashboard):
    def __init__(self, *args):
        super().__init__(*args)
        QTimer.singleShot(500, self.report_ready)
        QTimer.singleShot(15000, self.quit_app)

    def report_ready(self):
        print(
            "READY" if self.shortcut_status() and self.tray.isVisible() else "NOT_READY", flush=True
        )

    def show_panel(self):
        super().show_panel()
        print("ACTIVATED", flush=True)
        QTimer.singleShot(100, self.quit_app)


app_module.Dashboard = ObservedDashboard
raise SystemExit(app_module.main())
