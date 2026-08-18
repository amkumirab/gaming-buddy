from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QPixmap
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
from gaming_buddy.models import Card, CardKind
from gaming_buddy.pin import PinWidget
from gaming_buddy.storage import CardStore


class Dashboard(QMainWindow):
    request_quit = Signal()

    def __init__(self, store: CardStore, captures_dir: Path) -> None:
        super().__init__()
        self.store = store
        self.captures_dir = captures_dir
        self.settings = QSettings("GamingBuddy", "GamingBuddy")
        self.pins: dict[int, PinWidget] = {}
        self.capture_overlay: SelectionOverlay | None = None
        self._really_quit = False

        self.setWindowTitle("Gaming Buddy")
        self.setMinimumSize(430, 690)
        self.resize(470, 760)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._build_ui()
        self._build_tray()
        self._restore_settings()
        self.refresh_cards()

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

        self.click_through = QCheckBox("Click-through pins  (Ctrl+Shift+L)")
        self.click_through.toggled.connect(self.set_click_through)
        layout.addWidget(self.click_through)

        library_header = QHBoxLayout()
        library_label = QLabel("SAVED CARDS")
        library_label.setObjectName("section")
        self.filter_current = QCheckBox("Current game only")
        self.filter_current.toggled.connect(self.refresh_cards)
        library_header.addWidget(library_label)
        library_header.addStretch(1)
        library_header.addWidget(self.filter_current)
        layout.addLayout(library_header)

        self.card_list = QListWidget()
        self.card_list.itemDoubleClicked.connect(self._pin_selected)
        self.card_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.card_list.customContextMenuRequested.connect(self._library_menu)
        layout.addWidget(self.card_list, 1)

        footer = QLabel("Ctrl+Shift+G panel  •  Ctrl+Shift+S capture  •  Double-click to pin")
        footer.setObjectName("muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
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
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(capture_action)
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

    def _save_capture(self, pixmap: QPixmap) -> None:
        now = datetime.now(UTC).astimezone()
        timestamp = now.strftime("%Y%m%d-%H%M%S-%f")
        path = self.captures_dir / f"capture-{timestamp}.png"
        if not pixmap.save(str(path), "PNG"):
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
            width=max(240, min(520, pixmap.width())),
            height=max(150, min(380, pixmap.height() + 45)),
        )
        self.store.add(card)
        self.show_pin(card)
        self.refresh_cards()
        self.show_panel()
        self.statusBar().showMessage("Screenshot captured and pinned", 3000)

    def show_pin(self, card: Card) -> None:
        if card.id is None:
            return
        existing = self.pins.get(card.id)
        if existing is not None:
            existing.show()
            existing.raise_()
            return
        pin = PinWidget(card, self._save_pin_layout, self._delete_card)
        pin.set_click_through(self.click_through.isChecked())
        self.pins[card.id] = pin
        pin.show()

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
        self.card_list.clear()
        for card in self.store.list(game):
            icon = "▣" if card.kind is CardKind.IMAGE else "◆"
            game_label = card.game or "General"
            item = QListWidgetItem(f"{icon}  {card.title}\n     {game_label}")
            item.setData(Qt.ItemDataRole.UserRole, card.id)
            item.setToolTip("Double-click to pin")
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
        menu = QMenu(self)
        pin_action = menu.addAction("Pin card")
        delete_action = menu.addAction("Delete card")
        action = menu.exec(self.card_list.mapToGlobal(position))  # type: ignore[arg-type]
        if action is pin_action:
            self._pin_selected(item)
        elif action is delete_action:
            card = self._selected_card()
            if card is not None:
                self._delete_card(card)

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
                "Use Ctrl+Shift+G or the tray icon to bring it back.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def quit_app(self) -> None:
        self._really_quit = True
        self.request_quit.emit()
        QApplication.quit()
