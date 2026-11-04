from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QSignalSpy, QTest

from gaming_buddy.capture_button import CaptureButton
from gaming_buddy.theme import STYLESHEET


def test_split_button_main_and_arrow_menu_are_separate_keyboard_actions(qt_application):
    button = CaptureButton()
    button.setStyleSheet(STYLESHEET)
    events = []
    button.capture_requested.connect(lambda: events.append("area"))
    button.text_requested.connect(lambda: events.append("text"))
    try:
        button.resize(button.sizeHint())
        button.show()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=QPoint(16, button.height() // 2))
        assert events == ["area"]

        def choose_text():
            menu = button.menu()
            menu.setActiveAction(button.text_action)
            QTest.keyClick(menu, Qt.Key.Key_Return)

        QTimer.singleShot(20, choose_text)
        selected = QSignalSpy(button.text_requested)
        QTest.mouseClick(
            button, Qt.MouseButton.LeftButton,
            pos=QPoint(button.width() - 4, button.height() // 2),
        )
        if selected.count() == 0:
            assert selected.wait(1000)
        assert events == ["area", "text"]
        assert button.menu().parent() is button
        assert button.accessibleName() and "arrow menu" in button.toolTip()
        assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    finally:
        button.menu().close()
        button.close()
        button.deleteLater()
