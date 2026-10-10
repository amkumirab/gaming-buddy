from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from gaming_buddy.dashboard import Dashboard
from gaming_buddy.hotkeys import GlobalHotkeys
from gaming_buddy.paths import asset_path, ensure_data_dirs
from gaming_buddy.single_instance import InstanceError, SingleInstance
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
    instance = SingleInstance(base_dir)
    try:
        try:
            if not instance.claim_or_notify():
                return 0
        except InstanceError as error:
            QMessageBox.warning(None, "Gaming Buddy", str(error))
            return 1
        store = CardStore(base_dir / "gaming-buddy.sqlite3")
        try:
            return _run_dashboard(app, store, captures_dir, instance)
        finally:
            store.close()
    finally:
        instance.close()


def _run_dashboard(
    app: QApplication,
    store: CardStore,
    captures_dir: Path,
    instance: SingleInstance,
) -> int:
    dashboard = Dashboard(store, captures_dir)
    hotkeys = GlobalHotkeys(dashboard.shortcuts)
    dashboard.shortcut_status = lambda: hotkeys.running
    hotkeys.toggle_panel.connect(dashboard.toggle_panel)
    hotkeys.quick_finder.connect(dashboard.show_quick_finder)
    hotkeys.capture_area.connect(dashboard.start_capture)
    hotkeys.capture_screen.connect(dashboard.start_full_screen_capture)
    hotkeys.toggle_click_through.connect(dashboard.toggle_click_through)
    hotkeys.toggle_focus_mode.connect(dashboard.toggle_focus_mode)
    hotkeys.previous_pin.connect(dashboard.show_previous_pin)
    hotkeys.next_pin.connect(dashboard.show_next_pin)
    hotkeys.restore_pins.connect(dashboard.restore_pin_cycle)
    hotkeys.failed.connect(dashboard.on_shortcuts_failed)
    dashboard.shortcut_editing_started.connect(hotkeys.stop)
    dashboard.shortcut_editing_cancelled.connect(hotkeys.start)
    dashboard.shortcuts_changed.connect(hotkeys.update_shortcuts)
    dashboard.request_quit.connect(hotkeys.stop)

    try:
        hotkeys.start()
        dashboard.show()
        instance.activation_requested.connect(dashboard.show_panel)
        instance.set_ready()
        return app.exec()
    finally:
        hotkeys.stop()


if __name__ == "__main__":
    raise SystemExit(main())
