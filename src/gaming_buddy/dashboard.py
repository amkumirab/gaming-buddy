from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QSettings, QSignalBlocker, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QIcon,
    QImage,
    QKeyEvent,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.capture import SelectionOverlay, begin_capture
from gaming_buddy.card_editor import CardEditor
from gaming_buddy.hotkeys import DEFAULT_SHORTCUTS, validate_shortcuts
from gaming_buddy.image_annotation import (
    AnnotationDialog,
    AnnotationSaveError,
    save_annotated_image,
)
from gaming_buddy.image_import import (
    ImageImport,
    ImageImportError,
    discard_duplicate_images,
    image_file_digest,
    load_clipboard_image,
    load_image_file,
    local_image_paths,
    save_imported_image,
)
from gaming_buddy.models import Card, CardKind
from gaming_buddy.onboarding import OnboardingDialog
from gaming_buddy.pin import PinWidget
from gaming_buddy.pin_visibility import PinVisibilityController
from gaming_buddy.profile_dialog import ProfileDialog
from gaming_buddy.profiles import (
    ActiveApplication,
    ActiveGameDetector,
    GameProfileStore,
    belongs_to_profile,
)
from gaming_buddy.shortcut_dialog import ShortcutDialog
from gaming_buddy.startup import StartupError, StartupManager
from gaming_buddy.storage import CardStore
from gaming_buddy.trash_dialog import TrashDialog, remove_card_image_if_unused
from gaming_buddy.workspace_backup import (
    BackupError,
    create_workspace_backup,
    inspect_workspace_backup,
    restore_workspace_backup,
)


class Dashboard(QMainWindow):
    request_quit = Signal()
    shortcut_editing_started = Signal()
    shortcut_editing_cancelled = Signal()
    shortcuts_changed = Signal(dict)

    def __init__(self, store: CardStore, captures_dir: Path) -> None:
        super().__init__()
        self.store = store
        self.captures_dir = captures_dir
        self.settings = QSettings("GamingBuddy", "GamingBuddy")
        self.startup_manager = StartupManager()
        self.shortcuts = self._load_shortcuts()
        self.profile_store = GameProfileStore(self.settings)
        self.active_application: ActiveApplication | None = None
        self._focused_game: str | None = None
        self.game_detector = ActiveGameDetector(self)
        self.game_detector.active_changed.connect(self._on_active_application)
        self.game_detector.foreground_changed.connect(self._on_foreground_application)
        self.pins: dict[int, PinWidget] = {}
        self._auto_hidden_pin_ids: set[int] = set()
        self.pin_visibility = PinVisibilityController(self)
        self.pin_visibility.auto_hide_requested.connect(self._hide_pins_automatically)
        self.pin_visibility.auto_restore_requested.connect(
            self._restore_pins_after_auto_hide
        )
        self.capture_overlay: SelectionOverlay | None = None
        self._really_quit = False
        self._last_deleted_card_id: int | None = None
        self.undo_timer = QTimer(self)
        self.undo_timer.setSingleShot(True)
        self.undo_timer.timeout.connect(self._hide_undo)

        self.setWindowTitle("Gaming Buddy")
        self.setMinimumSize(430, 730)
        self.resize(470, 900)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_tray()
        self._restore_settings()
        self.refresh_cards()
        QTimer.singleShot(0, self._purge_expired_trash)
        QTimer.singleShot(0, self.restore_workspace)
        QTimer.singleShot(0, self.game_detector.start)
        QTimer.singleShot(350, self._show_first_run_setup)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("panel")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        brand = QLabel("GAMING BUDDY")
        brand.setObjectName("brand")
        subtitle = QLabel("Your clues, builds and screenshots — always in reach.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(brand)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        game_label = QLabel("CURRENT GAME")
        game_label.setObjectName("section")
        self.game_input = QLineEdit()
        self.game_input.setPlaceholderText("e.g. Elden Ring")
        self.game_input.textChanged.connect(self._on_game_changed)
        layout.addWidget(game_label)
        layout.addWidget(self.game_input)

        profile_options = QHBoxLayout()
        self.auto_profiles = QCheckBox("Auto-switch game profiles")
        self.auto_profiles.toggled.connect(self.set_auto_profiles)
        manage_profiles = QPushButton("Profiles…")
        manage_profiles.clicked.connect(self.manage_profiles)
        profile_options.addWidget(self.auto_profiles)
        profile_options.addStretch(1)
        profile_options.addWidget(manage_profiles)
        layout.addLayout(profile_options)

        self.auto_hide_pins = QCheckBox("Hide pins when a linked game loses focus")
        self.auto_hide_pins.setToolTip(
            "Keeps pins off other apps and restores them when you return to a linked game."
        )
        self.auto_hide_pins.toggled.connect(self.set_auto_hide_pins)
        layout.addWidget(self.auto_hide_pins)

        detected_row = QHBoxLayout()
        self.detected_app = QLabel("Waiting for an active game…")
        self.detected_app.setObjectName("muted")
        self.detected_app.setToolTip(
            "Open a game, return with the panel shortcut, then link the detected executable."
        )
        link_profile = QPushButton("Link detected app")
        link_profile.clicked.connect(self.link_detected_application)
        detected_row.addWidget(self.detected_app, 1)
        detected_row.addWidget(link_profile)
        layout.addLayout(detected_row)

        note_label = QLabel("QUICK NOTE")
        note_label.setObjectName("section")
        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Door code, quest clue, build order…")
        self.note_input.setMaximumHeight(105)
        layout.addWidget(note_label)
        layout.addWidget(self.note_input)

        note_buttons = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_note)
        pin_button = QPushButton("Pin note")
        pin_button.clicked.connect(self.pin_note)
        capture_button = QPushButton("Capture area")
        capture_button.setObjectName("primary")
        capture_button.clicked.connect(self.start_capture)
        import_button = QPushButton("Import image…")
        import_button.setToolTip("Choose image files, drag them here, or paste with Ctrl+V")
        import_button.clicked.connect(self.choose_image_files)
        note_buttons.addWidget(save_button)
        note_buttons.addWidget(pin_button)
        note_buttons.addWidget(capture_button)
        note_buttons.addWidget(import_button)
        layout.addLayout(note_buttons)

        controls = QHBoxLayout()
        opacity_label = QLabel("New pin opacity")
        opacity_label.setObjectName("muted")
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(88)
        controls.addWidget(opacity_label)
        controls.addWidget(self.opacity_slider, 1)
        layout.addLayout(controls)

        self.click_through = QCheckBox()
        self.click_through.toggled.connect(self.set_click_through)
        layout.addWidget(self.click_through)

        workspace_controls = QHBoxLayout()
        show_pins = QPushButton("Show saved pins")
        show_pins.clicked.connect(self.show_all_pins)
        hide_pins = QPushButton("Hide all pins")
        hide_pins.clicked.connect(self.hide_all_pins)
        workspace_controls.addWidget(show_pins)
        workspace_controls.addWidget(hide_pins)
        layout.addLayout(workspace_controls)

        layout_controls = QHBoxLayout()
        collapse_pins = QPushButton("Collapse all")
        collapse_pins.clicked.connect(self.collapse_all_pins)
        expand_pins = QPushButton("Expand all")
        expand_pins.clicked.connect(self.expand_all_pins)
        unlock_pins = QPushButton("Unlock all")
        unlock_pins.clicked.connect(self.unlock_all_pins)
        layout_controls.addWidget(collapse_pins)
        layout_controls.addWidget(expand_pins)
        layout_controls.addWidget(unlock_pins)
        layout.addLayout(layout_controls)

        tools = QHBoxLayout()
        shortcuts_button = QPushButton("Shortcuts…")
        shortcuts_button.clicked.connect(self.edit_shortcuts)
        backup_button = QPushButton("Backup…")
        backup_button.clicked.connect(self.backup_workspace)
        restore_button = QPushButton("Restore…")
        restore_button.clicked.connect(self.restore_backup)
        getting_started_button = QPushButton("Getting started…")
        getting_started_button.clicked.connect(self.show_getting_started)
        tools.addWidget(shortcuts_button)
        tools.addWidget(backup_button)
        tools.addWidget(restore_button)
        tools.addWidget(getting_started_button)
        layout.addLayout(tools)

        library_header = QHBoxLayout()
        library_label = QLabel("SAVED CARDS")
        library_label.setObjectName("section")
        self.trash_button = QPushButton()
        self.trash_button.setObjectName("compact")
        self.trash_button.setToolTip("Open recently deleted cards")
        self.trash_button.clicked.connect(self.open_trash)
        self.filter_current = QCheckBox("Current game only")
        self.filter_current.toggled.connect(self.refresh_cards)
        self.filter_favorites = QCheckBox("Favorites")
        self.filter_favorites.toggled.connect(self.refresh_cards)
        library_header.addWidget(library_label)
        library_header.addWidget(self.trash_button)
        library_header.addStretch(1)
        library_header.addWidget(self.filter_favorites)
        library_header.addWidget(self.filter_current)
        layout.addLayout(library_header)

        self.search_cards = QLineEdit()
        self.search_cards.setPlaceholderText("Search titles, notes, and games…")
        self.search_cards.setClearButtonEnabled(True)
        self.search_cards.textChanged.connect(self.refresh_cards)
        layout.addWidget(self.search_cards)

        self.undo_bar = QFrame()
        self.undo_bar.setObjectName("undoBar")
        undo_layout = QHBoxLayout(self.undo_bar)
        undo_layout.setContentsMargins(10, 6, 6, 6)
        self.undo_label = QLabel()
        self.undo_label.setObjectName("muted")
        self.undo_label.setWordWrap(True)
        undo_button = QPushButton("Undo")
        undo_button.setObjectName("compact")
        undo_button.clicked.connect(self._undo_delete)
        undo_layout.addWidget(self.undo_label, 1)
        undo_layout.addWidget(undo_button)
        self.undo_bar.hide()
        layout.addWidget(self.undo_bar)

        self.card_list = QListWidget()
        self.card_list.itemDoubleClicked.connect(self._pin_selected)
        self.card_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.card_list.customContextMenuRequested.connect(self._library_menu)
        layout.addWidget(self.card_list, 1)

        self.shortcut_footer = QLabel()
        self.shortcut_footer.setObjectName("muted")
        self.shortcut_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.shortcut_footer.setWordWrap(True)
        layout.addWidget(self.shortcut_footer)
        self._update_shortcut_labels()

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        icon = QApplication.windowIcon()
        if icon.isNull():
            icon = QIcon.fromTheme("applications-games")
            if icon.isNull():
                pixmap = QPixmap(32, 32)
                pixmap.fill(Qt.GlobalColor.transparent)
                icon = QIcon(pixmap)
        self.tray.setIcon(icon)
        self.tray.setToolTip("Gaming Buddy")
        menu = QMenu()
        show_action = QAction("Show Gaming Buddy", menu)
        show_action.triggered.connect(self.show_panel)
        capture_action = QAction("Capture area", menu)
        capture_action.triggered.connect(self.start_capture)
        paste_image_action = QAction("Paste image", menu)
        paste_image_action.triggered.connect(self.paste_image)
        import_image_action = QAction("Import image…", menu)
        import_image_action.triggered.connect(self.choose_image_files)
        show_pins_action = QAction("Show saved pins", menu)
        show_pins_action.triggered.connect(self.show_all_pins)
        hide_pins_action = QAction("Hide all pins", menu)
        hide_pins_action.triggered.connect(self.hide_all_pins)
        collapse_pins_action = QAction("Collapse all pins", menu)
        collapse_pins_action.triggered.connect(self.collapse_all_pins)
        expand_pins_action = QAction("Expand all pins", menu)
        expand_pins_action.triggered.connect(self.expand_all_pins)
        unlock_pins_action = QAction("Unlock all pins", menu)
        unlock_pins_action.triggered.connect(self.unlock_all_pins)
        self.auto_hide_pins_action = QAction("Hide pins outside linked games", menu)
        self.auto_hide_pins_action.setCheckable(True)
        self.auto_hide_pins_action.triggered.connect(self.set_auto_hide_pins)
        shortcuts_action = QAction("Keyboard shortcuts…", menu)
        shortcuts_action.triggered.connect(self.edit_shortcuts)
        profiles_action = QAction("Game profiles…", menu)
        profiles_action.triggered.connect(self.manage_profiles)
        backup_action = QAction("Backup workspace…", menu)
        backup_action.triggered.connect(self.backup_workspace)
        restore_action = QAction("Restore backup…", menu)
        restore_action.triggered.connect(self.restore_backup)
        trash_action = QAction("Recently deleted…", menu)
        trash_action.triggered.connect(self.open_trash)
        getting_started_action = QAction("Getting started…", menu)
        getting_started_action.triggered.connect(self.show_getting_started)
        self.launch_at_sign_in_action = QAction("Launch at Windows sign-in", menu)
        self.launch_at_sign_in_action.setCheckable(True)
        self.launch_at_sign_in_action.setChecked(self.startup_manager.is_enabled())
        self.launch_at_sign_in_action.triggered.connect(self.set_launch_at_sign_in)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(capture_action)
        menu.addAction(paste_image_action)
        menu.addAction(import_image_action)
        menu.addSeparator()
        menu.addAction(show_pins_action)
        menu.addAction(hide_pins_action)
        menu.addAction(collapse_pins_action)
        menu.addAction(expand_pins_action)
        menu.addAction(unlock_pins_action)
        menu.addAction(self.auto_hide_pins_action)
        menu.addSeparator()
        menu.addAction(profiles_action)
        menu.addAction(shortcuts_action)
        menu.addSeparator()
        menu.addAction(backup_action)
        menu.addAction(restore_action)
        menu.addAction(trash_action)
        menu.addSeparator()
        menu.addAction(getting_started_action)
        menu.addAction(self.launch_at_sign_in_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.aboutToShow.connect(self._refresh_startup_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _restore_settings(self) -> None:
        self.game_input.setText(self.settings.value("game", ""))
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.click_through.setChecked(self.settings.value("click_through", False, type=bool))
        self.auto_profiles.setChecked(self.settings.value("profiles/auto_switch", False, type=bool))
        self.auto_hide_pins.setChecked(
            self.settings.value("profiles/auto_hide_pins", False, type=bool)
        )

    def _show_first_run_setup(self) -> None:
        completed = self.settings.value("onboarding/completed", False, type=bool)
        if completed:
            return
        self.show_getting_started()
        self.settings.setValue("onboarding/completed", True)
        self.settings.sync()

    def show_getting_started(self, _checked: bool = False) -> None:
        launch_at_sign_in = self.startup_manager.is_enabled()
        dialog = OnboardingDialog(self.shortcuts, launch_at_sign_in, self)
        if dialog.exec() and dialog.launch_at_sign_in != launch_at_sign_in:
            self.set_launch_at_sign_in(dialog.launch_at_sign_in)

    def set_launch_at_sign_in(self, enabled: bool) -> None:
        try:
            self.startup_manager.set_enabled(enabled)
        except StartupError as error:
            actual_state = self.startup_manager.is_enabled()
            blocker = QSignalBlocker(self.launch_at_sign_in_action)
            self.launch_at_sign_in_action.setChecked(actual_state)
            del blocker
            QMessageBox.warning(self, "Startup setting unavailable", str(error))
            return

        blocker = QSignalBlocker(self.launch_at_sign_in_action)
        self.launch_at_sign_in_action.setChecked(enabled)
        del blocker
        message = (
            "Gaming Buddy will launch at sign-in" if enabled else "Launch at sign-in disabled"
        )
        self.statusBar().showMessage(message, 3000)

    def _refresh_startup_action(self) -> None:
        blocker = QSignalBlocker(self.launch_at_sign_in_action)
        self.launch_at_sign_in_action.setChecked(self.startup_manager.is_enabled())
        del blocker

    def set_auto_profiles(self, enabled: bool) -> None:
        self.settings.setValue("profiles/auto_switch", enabled)
        if enabled and self.active_application is not None:
            game = self.profile_store.game_for(self.active_application.executable)
            if game:
                self._switch_game_profile(game)
        message = "Automatic profile switching enabled" if enabled else "Profile switching paused"
        self.statusBar().showMessage(message, 2500)

    def set_auto_hide_pins(self, enabled: bool) -> None:
        self.settings.setValue("profiles/auto_hide_pins", enabled)
        for control in (self.auto_hide_pins, self.auto_hide_pins_action):
            blocker = QSignalBlocker(control)
            control.setChecked(enabled)
            del blocker
        self.pin_visibility.set_enabled(enabled)
        message = (
            "Pins will hide outside linked games"
            if enabled
            else "Automatic pin hiding disabled"
        )
        self.statusBar().showMessage(message, 2500)

    def link_detected_application(self) -> None:
        application = self.game_detector.last_external_application
        if application is None:
            QMessageBox.information(
                self,
                "No game detected",
                "Open the game, return with the panel shortcut, then try again.",
            )
            return
        game = self.game_input.text().strip()
        if not game:
            QMessageBox.warning(self, "Game required", "Enter the current game name first.")
            self.game_input.setFocus()
            return
        self.profile_store.link(application.executable, game)
        self._focused_game = game
        self.pin_visibility.update_focus(True)
        self._update_detected_label(application)
        self.statusBar().showMessage(
            f"Linked {application.executable} to the {game} profile",
            3500,
        )

    def manage_profiles(self) -> None:
        dialog = ProfileDialog(self.profile_store.all(), self)
        if not dialog.exec():
            return
        self.profile_store.replace(dialog.profiles())
        if self.active_application is not None:
            self._update_detected_label(self.active_application)
            game = self.profile_store.game_for(self.active_application.executable)
            self._focused_game = game
            self.pin_visibility.update_focus(game is not None)
            if game and self.auto_profiles.isChecked():
                self._switch_game_profile(game)
        self.statusBar().showMessage("Game profiles updated", 2500)

    def _on_active_application(self, application: ActiveApplication) -> None:
        self.active_application = application
        self._update_detected_label(application)
        game = self.profile_store.game_for(application.executable)
        if game and self.auto_profiles.isChecked():
            self._switch_game_profile(game)

    def _on_foreground_application(self, application: ActiveApplication | None) -> None:
        game = (
            self.profile_store.game_for(application.executable)
            if application is not None
            else None
        )
        self._focused_game = game
        self.pin_visibility.update_focus(game is not None)

    def _update_detected_label(self, application: ActiveApplication) -> None:
        game = self.profile_store.game_for(application.executable)
        suffix = f" → {game}" if game else " · not linked"
        self.detected_app.setText(f"Detected: {application.executable}{suffix}")
        self.detected_app.setToolTip(application.title or application.executable)

    def _switch_game_profile(self, game: str) -> None:
        changed = self.game_input.text().strip().casefold() != game.casefold()
        if changed:
            self.game_input.setText(game)
        self._show_profile_workspace(game)
        if changed:
            self.statusBar().showMessage(f"Switched to {game} profile", 3000)

    def _show_profile_workspace(self, game: str) -> None:
        if self.pin_visibility.manually_hidden or self.pin_visibility.automatically_hidden:
            for pin in self.pins.values():
                pin.hide()
            return
        for card in self.store.list(pinned_only=True):
            visible = belongs_to_profile(card.game, game)
            pin = self.pins.get(card.id) if card.id is not None else None
            if visible:
                self.show_pin(card, persist=False)
            elif pin is not None:
                pin.hide()

    def _load_shortcuts(self) -> dict[str, str]:
        saved = {
            action: str(self.settings.value(f"shortcuts/{action}", default))
            for action, default in DEFAULT_SHORTCUTS.items()
        }
        try:
            return validate_shortcuts(saved)
        except ValueError:
            return DEFAULT_SHORTCUTS.copy()

    def edit_shortcuts(self) -> None:
        self.shortcut_editing_started.emit()
        dialog = ShortcutDialog(self.shortcuts, self)
        if not dialog.exec():
            self.shortcut_editing_cancelled.emit()
            return
        self.shortcuts = validate_shortcuts(dialog.shortcuts())
        for action, shortcut in self.shortcuts.items():
            self.settings.setValue(f"shortcuts/{action}", shortcut)
        self.settings.sync()
        self._update_shortcut_labels()
        self.shortcuts_changed.emit(self.shortcuts.copy())
        self.statusBar().showMessage("Global shortcuts updated", 3000)

    def _update_shortcut_labels(self) -> None:
        panel = self.shortcuts["toggle_panel"]
        capture = self.shortcuts["capture_area"]
        click_through = self.shortcuts["toggle_click_through"]
        if hasattr(self, "click_through"):
            self.click_through.setText(f"Click-through pins  ({click_through})")
        if hasattr(self, "shortcut_footer"):
            self.shortcut_footer.setText(
                f"{panel} panel  •  {capture} capture  •  Double-click to pin"
            )

    def backup_workspace(self) -> None:
        timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d")
        default_name = Path.home() / "Documents" / f"Gaming-Buddy-backup-{timestamp}.zip"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Backup workspace",
            str(default_name),
            "ZIP backup (*.zip)",
        )
        if not filename:
            return
        destination = Path(filename)
        if destination.suffix.casefold() != ".zip":
            destination = destination.with_suffix(".zip")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            summary = create_workspace_backup(destination, self.store, self.settings)
        except (BackupError, OSError) as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        missing = (
            f"\nMissing image files: {summary.missing_image_count}"
            if summary.missing_image_count
            else ""
        )
        QMessageBox.information(
            self,
            "Backup complete",
            f"Saved {summary.card_count} cards and {summary.image_count} images to:\n"
            f"{destination}{missing}",
        )

    def restore_backup(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Restore workspace backup",
            str(Path.home() / "Documents"),
            "ZIP backup (*.zip)",
        )
        if not filename:
            return
        source = Path(filename)
        try:
            summary = inspect_workspace_backup(source)
        except BackupError as exc:
            QMessageBox.warning(self, "Invalid backup", str(exc))
            return
        answer = QMessageBox.question(
            self,
            "Restore workspace backup",
            f"Backup created: {summary.created_at}\n"
            f"Cards: {summary.card_count}\n"
            f"Images: {summary.image_count}\n\n"
            "Cards will be merged with the current library and exact duplicates will be skipped. "
            "Current cards and images will not be deleted. Matching portable settings will be "
            "updated.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = restore_workspace_backup(
                source,
                self.store,
                self.captures_dir,
                self.settings,
            )
        except (BackupError, OSError) as exc:
            QMessageBox.warning(self, "Restore failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._reload_restored_settings()
        self.refresh_cards()
        self.restore_workspace()
        if self.active_application is not None:
            game = self.profile_store.game_for(self.active_application.executable)
            self._focused_game = game
            self.pin_visibility.update_focus(game is not None)
            if game and self.auto_profiles.isChecked():
                self._switch_game_profile(game)
        QMessageBox.information(
            self,
            "Restore complete",
            f"Imported cards: {result.imported_cards}\n"
            f"Duplicates skipped: {result.duplicate_cards}\n"
            f"Unavailable cards skipped: {result.skipped_cards}\n"
            f"Settings restored: {result.restored_settings}",
        )

    def _reload_restored_settings(self) -> None:
        self.shortcuts = self._load_shortcuts()
        self._update_shortcut_labels()
        self.shortcuts_changed.emit(self.shortcuts.copy())
        self.profile_store = GameProfileStore(self.settings)
        self.game_input.setText(str(self.settings.value("game", "")))
        self.click_through.setChecked(self.settings.value("click_through", False, type=bool))
        self.auto_profiles.setChecked(self.settings.value("profiles/auto_switch", False, type=bool))
        self.auto_hide_pins.setChecked(
            self.settings.value("profiles/auto_hide_pins", False, type=bool)
        )

    def _on_game_changed(self, value: str) -> None:
        self.settings.setValue("game", value)
        if self.filter_current.isChecked():
            self.refresh_cards()

    def _make_note(self) -> Card | None:
        content = self.note_input.toPlainText().strip()
        if not content:
            self.statusBar().showMessage("Write a note first", 2500)
            return None
        first_line = content.splitlines()[0]
        title = first_line[:38] + ("…" if len(first_line) > 38 else "")
        return Card(
            id=None,
            kind=CardKind.NOTE,
            game=self.game_input.text().strip() or "General",
            title=title,
            content=content,
            opacity=self.opacity_slider.value() / 100,
        )

    def save_note(self) -> None:
        card = self._make_note()
        if card is None:
            return
        self.store.add(card)
        self.note_input.clear()
        self.refresh_cards()
        self.statusBar().showMessage("Note saved", 2500)

    def pin_note(self) -> None:
        card = self._make_note()
        if card is None:
            return
        self.store.add(card)
        self.note_input.clear()
        self.show_pin(card)
        self.refresh_cards()

    def start_capture(self) -> None:
        self.hide()
        QTimer.singleShot(180, self._open_capture_overlay)

    def _open_capture_overlay(self) -> None:
        try:
            self.capture_overlay = begin_capture()
            self.capture_overlay.selected.connect(self._save_capture)
            self.capture_overlay.cancelled.connect(self.show_panel)
        except RuntimeError as exc:
            self.show_panel()
            QMessageBox.warning(self, "Capture failed", str(exc))

    def _save_capture(self, image: QImage) -> None:
        now = datetime.now(UTC).astimezone()
        timestamp = now.strftime("%Y%m%d-%H%M%S-%f")
        path = self.captures_dir / f"capture-{timestamp}.png"
        if not image.save(str(path), "PNG", 100):
            self.show_panel()
            QMessageBox.warning(self, "Capture failed", "Could not save the selected image.")
            return
        game = self.game_input.text().strip() or "General"
        card = Card(
            id=None,
            kind=CardKind.IMAGE,
            game=game,
            title=f"Capture · {now.strftime('%H:%M')}",
            image_path=str(path),
            opacity=self.opacity_slider.value() / 100,
            width=max(240, min(520, image.width())),
            height=max(150, min(380, image.height() + 45)),
        )
        self.store.add(card)
        self.show_pin(card)
        self.refresh_cards()
        self.show_panel()
        self.statusBar().showMessage(
            f"Saved lossless PNG · {image.width()} × {image.height()} px", 3500
        )

    def choose_image_files(self, _checked: bool = False) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Import images",
            str(Path.home() / "Pictures"),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if filenames:
            self._import_image_files([Path(filename) for filename in filenames])

    def paste_image(self, _checked: bool = False) -> None:
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        paths = local_image_paths(mime_data)
        if paths:
            self._import_image_files(paths)
            return
        if not mime_data.hasImage():
            self.statusBar().showMessage("Clipboard does not contain an image", 2500)
            return
        try:
            imported = load_clipboard_image(clipboard.image())
        except ImageImportError as exc:
            QMessageBox.warning(self, "Paste failed", str(exc))
            return
        self._import_images([imported])

    def _import_image_files(self, paths: list[Path]) -> None:
        imported: list[ImageImport] = []
        errors: list[str] = []
        for path in paths:
            try:
                imported.append(load_image_file(path))
            except ImageImportError as exc:
                errors.append(str(exc))
        if errors:
            details = "\n".join(f"• {message}" for message in errors[:6])
            if len(errors) > 6:
                details += f"\n• …and {len(errors) - 6} more"
            QMessageBox.warning(self, "Some images were skipped", details)
        if imported:
            self._import_images(imported)

    def _import_images(self, imported: list[ImageImport]) -> None:
        known_digests = self._known_image_digests()
        unique, duplicates = discard_duplicate_images(imported, known_digests)
        if not unique:
            message = "This image is already saved"
            if len(imported) > 1:
                message = "All selected images are already saved"
            self.statusBar().showMessage(f"{message}, including Recently Deleted", 3500)
            return

        pin_immediately = self._choose_image_import_action(unique, duplicates)
        if pin_immediately is None:
            return

        cards: list[Card] = []
        failures: list[str] = []
        game = self.game_input.text().strip() or "General"
        for candidate in unique:
            try:
                path = save_imported_image(candidate, self.captures_dir)
            except ImageImportError as exc:
                failures.append(f"{candidate.source_name}: {exc}")
                continue
            card = Card(
                id=None,
                kind=CardKind.IMAGE,
                game=game,
                title=candidate.title,
                image_path=str(path),
                opacity=self.opacity_slider.value() / 100,
                width=max(240, min(520, candidate.image.width())),
                height=max(150, min(380, candidate.image.height() + 45)),
            )
            self.store.add(card)
            cards.append(card)
            if pin_immediately:
                self.show_pin(card)

        self.refresh_cards()
        if failures:
            QMessageBox.warning(self, "Import incomplete", "\n".join(failures[:6]))
        if cards:
            action = "Imported and pinned" if pin_immediately else "Imported"
            skipped = f" · {duplicates} duplicate(s) skipped" if duplicates else ""
            self.statusBar().showMessage(f"{action} {len(cards)} image(s){skipped}", 4000)

    def _known_image_digests(self) -> set[str]:
        digests: set[str] = set()
        cards = [*self.store.list(), *self.store.list_deleted()]
        for card in cards:
            if card.kind is not CardKind.IMAGE or not card.image_path:
                continue
            digest = image_file_digest(Path(card.image_path))
            if digest:
                digests.add(digest)
        return digests

    def _choose_image_import_action(
        self, imported: list[ImageImport], duplicates: int
    ) -> bool | None:
        count = len(imported)
        first = imported[0]
        box = QMessageBox(self)
        box.setWindowTitle("Import image" if count == 1 else "Import images")
        box.setIconPixmap(
            QPixmap.fromImage(first.image).scaled(
                220,
                150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        if count == 1:
            box.setText(first.source_name)
            box.setInformativeText(
                f"{first.image.width()} × {first.image.height()} px\n"
                "Save this image to the current game or pin it immediately?"
            )
        else:
            duplicate_note = f"\n{duplicates} duplicate(s) will be skipped." if duplicates else ""
            box.setText(f"Import {count} images?")
            box.setInformativeText(
                "Save them to the current game or pin them immediately?" + duplicate_note
            )
        save_button = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        pin_button = box.addButton("Save and pin", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_button:
            return False
        if clicked is pin_button:
            return True
        return None

    def show_pin(self, card: Card, *, persist: bool = True) -> None:
        if card.id is None:
            return
        if persist:
            was_auto_hidden = self.pin_visibility.automatically_hidden
            self.pin_visibility.manual_show()
            if was_auto_hidden:
                self._restore_pins_after_auto_hide()
            self.store.update_pinned(card.id, True)
            card.pinned = True
        existing = self.pins.get(card.id)
        if existing is not None:
            existing.show()
            existing.raise_()
            if persist:
                self.refresh_cards()
            return
        pin = PinWidget(
            card,
            self._save_pin_layout,
            self._unpin_card,
            self._delete_card,
            self._edit_card,
            self._save_pin_lock,
            self._save_pin_collapsed,
            self._annotate_card,
            self._copy_card,
            self._open_card_location,
        )
        pin.set_click_through(self.click_through.isChecked())
        self.pins[card.id] = pin
        self._save_pin_layout(card)
        pin.show()
        if persist:
            self.refresh_cards()

    def restore_workspace(self) -> None:
        restored = 0
        for card in self.store.list(pinned_only=True):
            self.show_pin(card, persist=False)
            restored += 1
        if restored:
            self.statusBar().showMessage(f"Restored {restored} saved pin(s)", 3000)

    def show_all_pins(self) -> None:
        self.pin_visibility.manual_show()
        self._auto_hidden_pin_ids.clear()
        cards = self.store.list(pinned_only=True)
        for card in cards:
            self.show_pin(card, persist=False)
        self.statusBar().showMessage(f"Showing {len(cards)} saved pin(s)", 2500)

    def hide_all_pins(self) -> None:
        self.pin_visibility.manual_hide()
        self._auto_hidden_pin_ids.clear()
        for pin in self.pins.values():
            pin.hide()
        self.statusBar().showMessage("Pins hidden; workspace is still saved", 2500)

    def unlock_all_pins(self) -> None:
        unlocked = self.store.unlock_all_pins()
        for pin in self.pins.values():
            if pin.card.locked:
                pin.set_locked(False, notify=False)
        self.refresh_cards()
        message = f"Unlocked {unlocked} pin(s)" if unlocked else "No locked pins"
        self.statusBar().showMessage(message, 2500)

    def collapse_all_pins(self) -> None:
        self._set_all_pins_collapsed(True)

    def expand_all_pins(self) -> None:
        self._set_all_pins_collapsed(False)

    def _set_all_pins_collapsed(self, collapsed: bool) -> None:
        changed = self.store.set_all_pins_collapsed(collapsed)
        for pin in self.pins.values():
            if pin.card.collapsed != collapsed:
                pin.set_collapsed(collapsed, notify=False)
        self.refresh_cards()
        verb = "Collapsed" if collapsed else "Expanded"
        fallback = "All pins are already collapsed" if collapsed else "All pins are already expanded"
        message = f"{verb} {changed} pin(s)" if changed else fallback
        self.statusBar().showMessage(message, 2500)

    def _hide_pins_automatically(self) -> None:
        self._auto_hidden_pin_ids = {
            card_id for card_id, pin in self.pins.items() if pin.isVisible()
        }
        for pin in self.pins.values():
            pin.hide()
        if self._auto_hidden_pin_ids:
            self.statusBar().showMessage(
                "Pins hidden until you return to a linked game",
                2500,
            )

    def _restore_pins_after_auto_hide(self) -> None:
        if self.pin_visibility.manually_hidden:
            return
        if self.auto_profiles.isChecked() and self._focused_game:
            self._auto_hidden_pin_ids.clear()
            self._show_profile_workspace(self._focused_game)
            return
        cards = {
            card.id: card for card in self.store.list(pinned_only=True) if card.id is not None
        }
        restored = 0
        for card_id in self._auto_hidden_pin_ids:
            card = cards.get(card_id)
            if card is not None:
                self.show_pin(card, persist=False)
                restored += 1
        self._auto_hidden_pin_ids.clear()
        if restored:
            self.statusBar().showMessage(f"Restored {restored} pin(s)", 2500)

    def _unpin_card(self, card: Card) -> None:
        if card.id is None:
            return
        pin = self.pins.pop(card.id, None)
        if pin is not None:
            pin.close()
            pin.deleteLater()
        self.store.update_pinned(card.id, False)
        card.pinned = False
        self.refresh_cards()
        self.statusBar().showMessage("Card unpinned and kept in the library", 2500)

    def _save_pin_layout(self, card: Card) -> None:
        if card.id is None:
            return
        self.store.update_layout(
            card.id,
            x=card.x,
            y=card.y,
            width=card.width,
            height=card.height,
            opacity=card.opacity,
        )

    def _save_pin_lock(self, card: Card) -> None:
        if card.id is None:
            return
        self.store.update_locked(card.id, card.locked)
        self.refresh_cards()
        message = "Pin locked" if card.locked else "Pin unlocked"
        self.statusBar().showMessage(message, 2000)

    def _save_pin_collapsed(self, card: Card) -> None:
        if card.id is None:
            return
        self.store.update_collapsed(card.id, card.collapsed)
        self.refresh_cards()
        message = "Pin collapsed" if card.collapsed else "Pin expanded"
        self.statusBar().showMessage(message, 2000)

    def refresh_cards(self) -> None:
        if not hasattr(self, "card_list"):
            return
        game = self.game_input.text() if self.filter_current.isChecked() else None
        query = self.search_cards.text()
        self.card_list.clear()
        for card in self.store.list(game, query, self.filter_favorites.isChecked()):
            kind_icon = "▣" if card.kind is CardKind.IMAGE else "◆"
            favorite_icon = "★ " if card.favorite else ""
            pinned_icon = "● " if card.pinned else ""
            icon = f"{pinned_icon}{favorite_icon}{kind_icon}"
            game_label = card.game or "General"
            workspace_label = " · Pinned" if card.pinned else ""
            lock_label = " · Locked" if card.pinned and card.locked else ""
            collapsed_label = " · Collapsed" if card.pinned and card.collapsed else ""
            item = QListWidgetItem(
                f"{icon}  {card.title}\n     "
                f"{game_label}{workspace_label}{lock_label}{collapsed_label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, card.id)
            item.setToolTip(
                "Saved in the restored workspace" if card.pinned else "Double-click to pin"
            )
            self.card_list.addItem(item)
        self._update_trash_button()

    def _selected_card(self) -> Card | None:
        item = self.card_list.currentItem()
        if item is None:
            return None
        return self.store.get(int(item.data(Qt.ItemDataRole.UserRole)))

    def _pin_selected(self, item: QListWidgetItem) -> None:
        card = self.store.get(int(item.data(Qt.ItemDataRole.UserRole)))
        if card is not None:
            self.show_pin(card)

    def _library_menu(self, position: object) -> None:
        item = self.card_list.itemAt(position)  # type: ignore[arg-type]
        if item is None:
            return
        self.card_list.setCurrentItem(item)
        card = self._selected_card()
        if card is None:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit card…")
        copy_action = menu.addAction(
            "Copy image" if card.kind is CardKind.IMAGE else "Copy note text"
        )
        annotate_action = None
        open_location_action = None
        lock_action = None
        collapse_action = None
        if card.kind is CardKind.IMAGE:
            annotate_action = menu.addAction("Annotate image…")
            open_location_action = menu.addAction("Open file location")
        if card.pinned:
            collapse_action = menu.addAction(
                "Expand pin" if card.collapsed else "Collapse pin"
            )
            lock_action = menu.addAction("Unlock pin" if card.locked else "Lock pin position")
        menu.addSeparator()
        favorite_action = menu.addAction(
            "Remove from favorites" if card.favorite else "Add to favorites"
        )
        menu.addSeparator()
        pin_action = menu.addAction("Unpin card" if card.pinned else "Pin card")
        delete_action = menu.addAction("Move to trash")
        action = menu.exec(self.card_list.mapToGlobal(position))  # type: ignore[arg-type]
        if action is edit_action:
            self._edit_card(card)
        elif action is copy_action:
            self._copy_card(card)
        elif annotate_action is not None and action is annotate_action:
            self._annotate_card(card)
        elif open_location_action is not None and action is open_location_action:
            self._open_card_location(card)
        elif collapse_action is not None and action is collapse_action:
            card.collapsed = not card.collapsed
            pin = self.pins.get(card.id) if card.id is not None else None
            if pin is not None:
                pin.set_collapsed(card.collapsed, notify=False)
            self._save_pin_collapsed(card)
        elif lock_action is not None and action is lock_action:
            card.locked = not card.locked
            pin = self.pins.get(card.id) if card.id is not None else None
            if pin is not None:
                pin.set_locked(card.locked, notify=False)
            self._save_pin_lock(card)
        elif action is favorite_action:
            self.store.update_favorite(card.id, not card.favorite)
            self.refresh_cards()
        elif action is pin_action:
            if card.pinned:
                self._unpin_card(card)
            else:
                self._pin_selected(item)
        elif action is delete_action:
            self._delete_card(card)

    def _edit_card(self, card: Card) -> None:
        if card.id is None:
            return
        pin = self.pins.get(card.id)
        was_visible = pin.isVisible() if pin is not None else False
        if pin is not None:
            pin.save_now()

        dialog = CardEditor(card, self)
        if not dialog.exec():
            return
        title, game, content = dialog.values()
        if not self.store.update_details(
            card.id,
            title=title,
            game=game or "General",
            content=content,
        ):
            QMessageBox.warning(self, "Edit failed", "The selected card no longer exists.")
            return

        updated = self.store.get(card.id)
        if updated is None:
            return
        if pin is not None:
            self.pins.pop(card.id, None)
            pin.close()
            pin.deleteLater()
            self.show_pin(updated, persist=False)
            if not was_visible:
                self.pins[card.id].hide()
        self.refresh_cards()
        self.statusBar().showMessage("Card updated", 2500)

    def _copy_card(self, card: Card) -> None:
        clipboard = QApplication.clipboard()
        if card.kind is CardKind.NOTE:
            clipboard.setText(card.content)
            self.statusBar().showMessage("Note copied to clipboard", 2500)
            return

        image = QImage(card.image_path)
        if image.isNull():
            QMessageBox.warning(self, "Copy failed", "The screenshot file could not be found.")
            return
        clipboard.setImage(image)
        self.statusBar().showMessage("Screenshot copied to clipboard", 2500)

    def _annotate_card(self, card: Card) -> None:
        source_path = Path(card.image_path)
        if card.kind is not CardKind.IMAGE or not source_path.is_file():
            QMessageBox.warning(
                self,
                "Image unavailable",
                "The screenshot file could not be found.",
            )
            return
        try:
            dialog = AnnotationDialog(source_path, self)
        except ValueError as exc:
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        if not dialog.exec():
            return

        image = dialog.annotated_image
        try:
            destination = save_annotated_image(image, self.captures_dir)
        except AnnotationSaveError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return

        annotated = Card(
            id=None,
            kind=CardKind.IMAGE,
            game=card.game or "General",
            title=f"{card.title} · Annotated"[:120],
            image_path=str(destination),
            opacity=card.opacity,
            width=max(240, min(520, image.width())),
            height=max(150, min(380, image.height() + 45)),
        )
        try:
            self.store.add(annotated)
        except sqlite3.Error:
            destination.unlink(missing_ok=True)
            QMessageBox.warning(
                self,
                "Save failed",
                "The annotated copy could not be added to the library.",
            )
            return

        if dialog.pin_after_save:
            self.show_pin(annotated)
        self.refresh_cards()
        message = (
            "Annotated copy saved and pinned"
            if dialog.pin_after_save
            else "Annotated copy saved"
        )
        self.statusBar().showMessage(message, 3500)

    def _open_card_location(self, card: Card) -> None:
        path = Path(card.image_path)
        if card.kind is not CardKind.IMAGE or not path.is_file():
            QMessageBox.warning(self, "File unavailable", "The screenshot file could not be found.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
            QMessageBox.warning(self, "Open failed", "The screenshot folder could not be opened.")

    def _delete_card(self, card: Card) -> None:
        if card.id is None:
            return
        if not self.store.move_to_trash(card.id):
            self.statusBar().showMessage("The selected card is no longer available", 2500)
            return
        pin = self.pins.pop(card.id, None)
        if pin is not None:
            pin.close()
            pin.deleteLater()
        self._last_deleted_card_id = card.id
        self.undo_label.setText(f'“{card.title}” moved to Recently Deleted')
        self.undo_bar.show()
        self.undo_timer.start(10000)
        self.refresh_cards()

    def _undo_delete(self) -> None:
        card_id = self._last_deleted_card_id
        if card_id is None or not self.store.restore(card_id):
            self._hide_undo()
            self.statusBar().showMessage("This card can no longer be restored", 2500)
            return
        self._hide_undo()
        self.refresh_cards()
        self.statusBar().showMessage("Card restored", 2500)

    def _hide_undo(self) -> None:
        self.undo_timer.stop()
        self._last_deleted_card_id = None
        if hasattr(self, "undo_bar"):
            self.undo_bar.hide()

    def open_trash(self, _checked: bool = False) -> None:
        self._purge_expired_trash()
        dialog = TrashDialog(self.store, self.captures_dir, self)
        dialog.exec()
        if (
            self._last_deleted_card_id is not None
            and self.store.get_deleted(self._last_deleted_card_id) is None
        ):
            self._hide_undo()
        self.refresh_cards()

    def _update_trash_button(self) -> None:
        if hasattr(self, "trash_button"):
            self.trash_button.setText(f"Deleted ({self.store.deleted_count()})")

    def _purge_expired_trash(self) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat(timespec="seconds")
        cards = self.store.purge_deleted_before(cutoff)
        for card in cards:
            remove_card_image_if_unused(self.store, card, self.captures_dir)
        if cards:
            self.refresh_cards()
            self.statusBar().showMessage(
                f"Permanently removed {len(cards)} expired deleted card(s)", 3000
            )

    def set_click_through(self, enabled: bool) -> None:
        self.settings.setValue("click_through", enabled)
        for pin in self.pins.values():
            pin.set_click_through(enabled)
        message = "Pins are click-through" if enabled else "Pins are interactive"
        self.statusBar().showMessage(message, 2500)

    def toggle_click_through(self) -> None:
        self.click_through.setChecked(not self.click_through.isChecked())

    def toggle_panel(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show_panel()

    def show_panel(self) -> None:
        self.game_detector.poll_now()
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if local_image_paths(event.mimeData()):
            event.acceptProposedAction()
            self.statusBar().showMessage("Drop image files to import them")
            return
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.statusBar().clearMessage()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = local_image_paths(event.mimeData())
        if not paths:
            super().dropEvent(event)
            return
        event.acceptProposedAction()
        self.statusBar().clearMessage()
        self._import_image_files(paths)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            mime_data = QApplication.clipboard().mimeData()
            if mime_data.hasImage() or local_image_paths(mime_data):
                self.paste_image()
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("window_geometry", self.saveGeometry())
        if self._really_quit:
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Gaming Buddy is still running",
                f"Use {self.shortcuts['toggle_panel']} or the tray icon to bring it back.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def quit_app(self) -> None:
        self.game_detector.stop()
        for pin in self.pins.values():
            pin.save_now()
        self._really_quit = True
        self.request_quit.emit()
        QApplication.quit()
