from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gaming_buddy.dashboard import Dashboard
from gaming_buddy.hotkeys import GlobalHotkeys
from gaming_buddy.paths import asset_path, ensure_data_dirs
from gaming_buddy.storage import CardStore
from gaming_buddy.theme import STYLESHEET


def main() -> int:
    QCoreApplication.setApplicationName("Gaming Buddy")
    QCoreApplication.setOrganizationName("GamingBuddy")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(str(asset_path("app-icon.png"))))

    base_dir, captures_dir = ensure_data_dirs()
    store = CardStore(base_dir / "gaming-buddy.sqlite3")
    dashboard = Dashboard(store, captures_dir)
    hotkeys = GlobalHotkeys()
    hotkeys.toggle_panel.connect(dashboard.toggle_panel)
    hotkeys.capture_area.connect(dashboard.start_capture)
    hotkeys.toggle_click_through.connect(dashboard.toggle_click_through)
    hotkeys.failed.connect(
        lambda message: dashboard.statusBar().showMessage(
            f"Global shortcuts unavailable: {message}"
        )
    )
    dashboard.request_quit.connect(hotkeys.stop)

    hotkeys.start()
    dashboard.show()
    exit_code = app.exec()
    hotkeys.stop()
    store.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
