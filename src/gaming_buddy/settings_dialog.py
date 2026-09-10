from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.hotkeys import DEFAULT_SHORTCUTS, SHORTCUT_LABELS, validate_shortcuts

DEFAULT_PIN_OPACITY = 88
DEFAULT_FOCUS_OPACITY = 70


@dataclass(frozen=True)
class SettingsSnapshot:
    launch_at_sign_in: bool
    automatic_update_checks: bool
    auto_switch_profiles: bool
    auto_hide_pins: bool
    click_through_pins: bool
    default_pin_opacity: int
    focus_opacity: int
    shortcuts: dict[str, str]


class SettingsDialog(QDialog):
    def __init__(
        self,
        values: SettingsSnapshot,
        *,
        version: str,
        storage_path: Path,
        startup_supported: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._storage_path = storage_path
        self.setWindowTitle("Gaming Buddy settings")
        self.setModal(True)
        self.setMinimumSize(590, 560)

        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(values, startup_supported), "General")
        tabs.addTab(self._build_overlay_tab(values), "Overlay")
        tabs.addTab(self._build_profiles_tab(values), "Game profiles")
        tabs.addTab(self._build_shortcuts_tab(values.shortcuts), "Shortcuts")
        tabs.addTab(self._build_about_tab(version, storage_path), "About")
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        restore = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        restore.clicked.connect(self.restore_defaults)
        layout.addWidget(buttons)

    def _build_general_tab(
        self, values: SettingsSnapshot, startup_supported: bool
    ) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.launch_at_sign_in = QCheckBox("Launch Gaming Buddy at Windows sign-in")
        self.launch_at_sign_in.setChecked(values.launch_at_sign_in)
        self.launch_at_sign_in.setEnabled(startup_supported)
        if not startup_supported:
            self.launch_at_sign_in.setToolTip("This option is available only on Windows.")
        self.automatic_update_checks = QCheckBox("Check for updates automatically")
        self.automatic_update_checks.setChecked(values.automatic_update_checks)
        update_note = QLabel(
            "Automatic checks run at most once per day. Updates are downloaded or installed "
            "only after you approve them."
        )
        update_note.setObjectName("muted")
        update_note.setWordWrap(True)
        layout.addWidget(self.launch_at_sign_in)
        layout.addWidget(self.automatic_update_checks)
        layout.addWidget(update_note)
        layout.addStretch(1)
        return tab

    def _build_overlay_tab(self, values: SettingsSnapshot) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.click_through_pins = QCheckBox("Make pins click-through")
        self.click_through_pins.setChecked(values.click_through_pins)
        layout.addWidget(self.click_through_pins)

        opacity_group = QGroupBox("Opacity")
        form = QFormLayout(opacity_group)
        self.default_pin_opacity = self._opacity_control(
            values.default_pin_opacity, "defaultPinOpacityValue"
        )
        self.focus_opacity = self._opacity_control(values.focus_opacity, "focusOpacityValue")
        form.addRow("New pins", self.default_pin_opacity[0])
        form.addRow("Focus mode", self.focus_opacity[0])
        layout.addWidget(opacity_group)
        note = QLabel("Opacity changes affect new pins and the temporary focus mode appearance.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return tab

    def _opacity_control(self, value: int, label_name: str) -> tuple[QWidget, QSlider]:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(30, 100)
        slider.setValue(min(100, max(30, value)))
        label = QLabel(f"{slider.value()}%")
        label.setObjectName(label_name)
        label.setMinimumWidth(42)
        slider.valueChanged.connect(lambda current: label.setText(f"{current}%"))
        row.addWidget(slider, 1)
        row.addWidget(label)
        return container, slider

    def _build_profiles_tab(self, values: SettingsSnapshot) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.auto_switch_profiles = QCheckBox("Switch profiles when the active game changes")
        self.auto_switch_profiles.setChecked(values.auto_switch_profiles)
        self.auto_hide_pins = QCheckBox("Hide pins when a linked game loses focus")
        self.auto_hide_pins.setChecked(values.auto_hide_pins)
        note = QLabel(
            "Executable links and named layouts remain available through the Profiles and "
            "Layouts controls in the main panel."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(self.auto_switch_profiles)
        layout.addWidget(self.auto_hide_pins)
        layout.addWidget(note)
        layout.addStretch(1)
        return tab

    def _build_shortcuts_tab(self, shortcuts: dict[str, str]) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel(
            "Choose shortcuts that work from anywhere. Each shortcut needs at least one "
            "modifier key."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self._shortcut_editors: dict[str, QKeySequenceEdit] = {}
        for action, label in SHORTCUT_LABELS.items():
            editor = QKeySequenceEdit(QKeySequence(shortcuts[action]))
            editor.setMaximumSequenceLength(1)
            editor.setClearButtonEnabled(True)
            self._shortcut_editors[action] = editor
            form.addRow(label, editor)
        layout.addLayout(form)
        restore = QPushButton("Restore shortcut defaults")
        restore.clicked.connect(self._restore_shortcut_defaults)
        layout.addWidget(restore)
        layout.addStretch(1)
        return tab

    def _build_about_tab(self, version: str, storage_path: Path) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        name = QLabel("Gaming Buddy")
        name.setObjectName("dialogTitle")
        description = QLabel("A lightweight in-game notebook and screenshot overlay for Windows.")
        description.setWordWrap(True)
        version_label = QLabel(f"Version {version}")
        version_label.setObjectName("muted")
        storage_label = QLabel("Local data folder")
        storage_label.setObjectName("section")
        path_row = QHBoxLayout()
        path = QLineEdit(str(storage_path))
        path.setReadOnly(True)
        path.setAccessibleName("Local data folder")
        open_folder = QPushButton("Open folder")
        open_folder.clicked.connect(self._open_storage_folder)
        path_row.addWidget(path, 1)
        path_row.addWidget(open_folder)
        ownership = QLabel(
            "Copyright © Amir Ali Mirab Zadeh Ardekani. All rights reserved.\n"
            "Proprietary software — copying, redistribution, and commercial use are not "
            "permitted without written authorization."
        )
        ownership.setWordWrap(True)
        layout.addWidget(name)
        layout.addWidget(description)
        layout.addWidget(version_label)
        layout.addSpacing(16)
        layout.addWidget(storage_label)
        layout.addLayout(path_row)
        layout.addSpacing(16)
        layout.addWidget(ownership)
        layout.addStretch(1)
        return tab

    def values(self) -> SettingsSnapshot:
        shortcuts = {
            action: editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for action, editor in self._shortcut_editors.items()
        }
        return SettingsSnapshot(
            launch_at_sign_in=self.launch_at_sign_in.isChecked(),
            automatic_update_checks=self.automatic_update_checks.isChecked(),
            auto_switch_profiles=self.auto_switch_profiles.isChecked(),
            auto_hide_pins=self.auto_hide_pins.isChecked(),
            click_through_pins=self.click_through_pins.isChecked(),
            default_pin_opacity=self.default_pin_opacity[1].value(),
            focus_opacity=self.focus_opacity[1].value(),
            shortcuts=validate_shortcuts(shortcuts),
        )

    def accept(self) -> None:
        try:
            self.values()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid shortcuts", str(error))
            return
        super().accept()

    def restore_defaults(self) -> None:
        self.launch_at_sign_in.setChecked(False)
        self.automatic_update_checks.setChecked(True)
        self.auto_switch_profiles.setChecked(False)
        self.auto_hide_pins.setChecked(False)
        self.click_through_pins.setChecked(False)
        self.default_pin_opacity[1].setValue(DEFAULT_PIN_OPACITY)
        self.focus_opacity[1].setValue(DEFAULT_FOCUS_OPACITY)
        self._restore_shortcut_defaults()

    def _restore_shortcut_defaults(self) -> None:
        for action, shortcut in DEFAULT_SHORTCUTS.items():
            self._shortcut_editors[action].setKeySequence(QKeySequence(shortcut))

    def _open_storage_folder(self) -> None:
        try:
            self._storage_path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.warning(self, "Could not open folder", str(error))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._storage_path))):
            QMessageBox.warning(self, "Could not open folder", "The data folder could not be opened.")
