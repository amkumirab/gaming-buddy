from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

_PREFIX = "onboarding/walkthrough/"
STEP_COUNT = 4


def _integer(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return default


@dataclass
class WalkthroughProgress:
    step: int = 0
    skipped: tuple[int, ...] = ()
    note_id: int | None = None
    paused: bool = True

    @classmethod
    def load(cls, settings: QSettings) -> WalkthroughProgress:
        step = _integer(settings.value(_PREFIX + "step"), 0)
        if not 0 <= step <= STEP_COUNT:
            step = 0
        skipped = settings.value(_PREFIX + "skipped", [])
        if not isinstance(skipped, (list, tuple)):
            skipped = [skipped]
        note_id = _integer(settings.value(_PREFIX + "note_id"), 0)
        return cls(
            step=step,
            skipped=tuple(sorted({number for item in skipped
                                  if 0 <= (number := _integer(item, -1)) < step})),
            note_id=note_id if note_id > 0 else None,
            paused=settings.value(_PREFIX + "paused", True, type=bool),
        )

    def save(self, settings: QSettings) -> None:
        settings.setValue(_PREFIX + "step", self.step)
        settings.setValue(_PREFIX + "skipped", list(self.skipped))
        settings.setValue(_PREFIX + "note_id", self.note_id or 0)
        settings.setValue(_PREFIX + "paused", self.paused)
        settings.sync()

    def advance(self, *, skip: bool = False) -> None:
        if self.step < STEP_COUNT:
            if skip:
                self.skipped += (self.step,)
            self.step += 1


class WalkthroughPanel(QFrame):
    action_requested = Signal()
    skip_requested = Signal()
    pause_requested = Signal()
    reference_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sectionCard")
        self.setAccessibleName("Getting started walkthrough")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        self.heading = QLabel()
        self.heading.setObjectName("sectionTitle")
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setObjectName("muted")
        for label in (self.heading, self.description):
            label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.heading)
        layout.addWidget(self.description)
        actions = QHBoxLayout()
        self.action_button = QPushButton()
        self.skip_button = QPushButton("Skip step")
        self.pause_button = QPushButton("Later")
        self.reference_button = QPushButton("Guide…")
        for button, name, signal in (
            (self.action_button, "Try this step", self.action_requested),
            (self.skip_button, "Skip this walkthrough step", self.skip_requested),
            (self.pause_button, "Dismiss walkthrough", self.pause_requested),
            (self.reference_button, "Open reference guide", self.reference_requested),
        ):
            button.setObjectName("compact")
            button.setAccessibleName(name)
            button.clicked.connect(signal.emit)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.hide()

    def set_step(self, step: int, title: str, description: str, action: str) -> None:
        finished = step == STEP_COUNT
        self.heading.setText(title if finished else f"{step + 1} of {STEP_COUNT} · {title}")
        self.description.setText(description)
        self.action_button.setText(action)
        self.action_button.setAccessibleName(action)
        self.skip_button.setVisible(not finished)
        self.pause_button.setText("Finish" if finished else "Later")
