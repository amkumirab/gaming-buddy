from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from gaming_buddy.dashboard import Dashboard
from gaming_buddy.hotkeys import GlobalHotkeys
from gaming_buddy.paths import asset_path, ensure_data_dirs
from gaming_buddy.storage import CardStore
from gaming_buddy.theme import STYLESHEET


def main() -> int:
    QCoreApplication.setApplicationName("Gaming Buddy")
    QCoreApplication.setOrganizationName("GamingBuddy")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(str(asset_path("app-icon.png"))))

    base_dir, captures_dir = ensure_data_dirs()
    store = CardStore(base_dir / "gaming-buddy.sqlite3")
    dashboard = Dashboard(store, captures_dir)
    hotkeys = GlobalHotkeys(dashboard.shortcuts)
    hotkeys.toggle_panel.connect(dashboard.toggle_panel)
    hotkeys.quick_finder.connect(dashboard.show_quick_finder)
    hotkeys.capture_area.connect(dashboard.start_capture)
    hotkeys.toggle_click_through.connect(dashboard.toggle_click_through)
    hotkeys.failed.connect(
        lambda message: dashboard.statusBar().showMessage(
            f"Global shortcuts unavailable: {message}"
        )
    )
    dashboard.shortcut_editing_started.connect(hotkeys.stop)
    dashboard.shortcut_editing_cancelled.connect(hotkeys.start)
    dashboard.shortcuts_changed.connect(hotkeys.update_shortcuts)
    dashboard.request_quit.connect(hotkeys.stop)

    hotkeys.start()
    dashboard.show()
    exit_code = app.exec()
    hotkeys.stop()
    store.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
