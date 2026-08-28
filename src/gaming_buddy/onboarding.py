from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.paths import asset_path


class OnboardingDialog(QDialog):
    def __init__(
        self,
        shortcuts: Mapping[str, str],
        launch_at_sign_in: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Getting started · Gaming Buddy")
        self.setMinimumWidth(540)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(
            QPixmap(str(asset_path("app-icon.png"))).scaled(
                72,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        titles = QVBoxLayout()
        title = QLabel("Welcome to Gaming Buddy")
        title.setObjectName("setupTitle")
        subtitle = QLabel("Keep the details you need within reach while you play.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addWidget(logo)
        header.addLayout(titles, 1)
        layout.addLayout(header)

        layout.addWidget(
            self._step(
                "1",
                "Capture or import a clue",
                f"Press {shortcuts['capture_area']}, drag around any map, code, or puzzle, "
                "then release to save a lossless screenshot. You can also drag image files "
                "onto the panel or paste an image with Ctrl+V.",
            )
        )
        layout.addWidget(
            self._step(
                "2",
                "Mark it up and keep it on screen",
                "Right-click an image to add arrows, text, or highlights. Then move and "
                "resize its pin, adjust opacity, or enable click-through when you want mouse "
                "input to reach the game.",
            )
        )
        layout.addWidget(
            self._step(
                "3",
                "Return without leaving the game",
                f"Press {shortcuts['toggle_panel']} to show or hide the panel. The tray icon "
                "keeps capture, pins, profiles, and this guide close by.",
            )
        )

        display_note = QLabel(
            "Best overlay experience: use Borderless Windowed mode. Exclusive Fullscreen "
            "games may appear above normal desktop overlays."
        )
        display_note.setObjectName("setupNotice")
        display_note.setWordWrap(True)
        layout.addWidget(display_note)

        self.launch_checkbox = QCheckBox("Launch Gaming Buddy when I sign in to Windows")
        self.launch_checkbox.setChecked(launch_at_sign_in)
        self.launch_checkbox.setToolTip(
            "Uses the current Windows account and does not require administrator access."
        )
        layout.addWidget(self.launch_checkbox)

        footer = QHBoxLayout()
        reminder = QLabel("You can reopen this guide from the panel or tray menu.")
        reminder.setObjectName("muted")
        reminder.setWordWrap(True)
        start_button = QPushButton("Start using Gaming Buddy")
        start_button.setObjectName("primary")
        start_button.clicked.connect(self.accept)
        start_button.setDefault(True)
        footer.addWidget(reminder, 1)
        footer.addWidget(start_button)
        layout.addLayout(footer)

    @property
    def launch_at_sign_in(self) -> bool:
        return self.launch_checkbox.isChecked()

    @staticmethod
    def _step(number: str, title: str, description: str) -> QFrame:
        card = QFrame()
        card.setObjectName("setupCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        badge = QLabel(number)
        badge.setObjectName("setupStep")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(32, 32)
        text = QVBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("setupHeading")
        body = QLabel(description)
        body.setObjectName("muted")
        body.setWordWrap(True)
        text.addWidget(heading)
        text.addWidget(body)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)
        return card
