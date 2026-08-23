from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
from gaming_buddy.models import Card, CardKind
from gaming_buddy.pin import PinWidget
from gaming_buddy.shortcut_dialog import ShortcutDialog
from gaming_buddy.storage import CardStore


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
        self.shortcuts = self._load_shortcuts()
        self.pins: dict[int, PinWidget] = {}
        self.capture_overlay: SelectionOverlay | None = None
        self._really_quit = False

        self.setWindowTitle("Gaming Buddy")
        self.setMinimumSize(430, 730)
        self.resize(470, 810)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._build_ui()
        self._build_tray()
        self._restore_settings()
        self.refresh_cards()
        QTimer.singleShot(0, self.restore_workspace)

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
        note_buttons.addWidget(save_button)
        note_buttons.addWidget(pin_button)
        note_buttons.addWidget(capture_button)
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

        shortcuts_button = QPushButton("Keyboard shortcuts…")
        shortcuts_button.clicked.connect(self.edit_shortcuts)
        layout.addWidget(shortcuts_button)

        library_header = QHBoxLayout()
        library_label = QLabel("SAVED CARDS")
        library_label.setObjectName("section")
        self.filter_current = QCheckBox("Current game only")
        self.filter_current.toggled.connect(self.refresh_cards)
        self.filter_favorites = QCheckBox("Favorites")
        self.filter_favorites.toggled.connect(self.refresh_cards)
        library_header.addWidget(library_label)
        library_header.addStretch(1)
        library_header.addWidget(self.filter_favorites)
        library_header.addWidget(self.filter_current)
        layout.addLayout(library_header)

        self.search_cards = QLineEdit()
        self.search_cards.setPlaceholderText("Search titles, notes, and games…")
        self.search_cards.setClearButtonEnabled(True)
        self.search_cards.textChanged.connect(self.refresh_cards)
        layout.addWidget(self.search_cards)

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
        show_pins_action = QAction("Show saved pins", menu)
        show_pins_action.triggered.connect(self.show_all_pins)
        hide_pins_action = QAction("Hide all pins", menu)
        hide_pins_action.triggered.connect(self.hide_all_pins)
        shortcuts_action = QAction("Keyboard shortcuts…", menu)
        shortcuts_action.triggered.connect(self.edit_shortcuts)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(capture_action)
        menu.addSeparator()
        menu.addAction(show_pins_action)
        menu.addAction(hide_pins_action)
        menu.addSeparator()
        menu.addAction(shortcuts_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _restore_settings(self) -> None:
        self.game_input.setText(self.settings.value("game", ""))
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.click_through.setChecked(self.settings.value("click_through", False, type=bool))

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

    def show_pin(self, card: Card, *, persist: bool = True) -> None:
        if card.id is None:
            return
        if persist:
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
        cards = self.store.list(pinned_only=True)
        for card in cards:
            self.show_pin(card, persist=False)
        self.statusBar().showMessage(f"Showing {len(cards)} saved pin(s)", 2500)

    def hide_all_pins(self) -> None:
        for pin in self.pins.values():
            pin.hide()
        self.statusBar().showMessage("Pins hidden; workspace is still saved", 2500)

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
            item = QListWidgetItem(f"{icon}  {card.title}\n     {game_label}{workspace_label}")
            item.setData(Qt.ItemDataRole.UserRole, card.id)
            item.setToolTip(
                "Saved in the restored workspace" if card.pinned else "Double-click to pin"
            )
            self.card_list.addItem(item)

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
        open_location_action = None
        if card.kind is CardKind.IMAGE:
            open_location_action = menu.addAction("Open file location")
        menu.addSeparator()
        favorite_action = menu.addAction(
            "Remove from favorites" if card.favorite else "Add to favorites"
        )
        menu.addSeparator()
        pin_action = menu.addAction("Unpin card" if card.pinned else "Pin card")
        delete_action = menu.addAction("Delete card")
        action = menu.exec(self.card_list.mapToGlobal(position))  # type: ignore[arg-type]
        if action is edit_action:
            self._edit_card(card)
        elif action is copy_action:
            self._copy_card(card)
        elif open_location_action is not None and action is open_location_action:
            self._open_card_location(card)
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
        pin = self.pins.pop(card.id, None)
        if pin is not None:
            pin.close()
            pin.deleteLater()
        self.store.delete(card.id)
        if card.kind is CardKind.IMAGE and card.image_path:
            try:
                Path(card.image_path).unlink(missing_ok=True)
            except OSError:
                pass
        self.refresh_cards()

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
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel()

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
        for pin in self.pins.values():
            pin.save_now()
        self._really_quit = True
        self.request_quit.emit()
        QApplication.quit()
