from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QMenu, QToolButton, QWidget


class CaptureButton(QToolButton):
    capture_requested = Signal()
    text_requested = Signal()

    def __init__(self, text: str = "Capture", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setObjectName("captureButton")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(text)
        description = "Capture a screen region. Open the arrow menu for Capture text."
        self.setToolTip(description)
        self.setAccessibleDescription(description)
        menu = QMenu(self)
        self.area_action = menu.addAction("Capture area")
        self.area_action.triggered.connect(self.capture_requested)
        self.text_action = menu.addAction("Capture text…")
        self.text_action.setToolTip("Capture a clue and review locally recognized text")
        self.text_action.triggered.connect(self.text_requested)
        self.setMenu(menu)
        self.clicked.connect(self.capture_requested)
