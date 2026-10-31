from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from gaming_buddy.quick_panel import QuickPanel
from gaming_buddy.theme import STYLESHEET


def test_compact_actions_and_note_keyboard_behavior(qt_application):
    panel = QuickPanel()
    events = []
    panel.capture_requested.connect(lambda: events.append("capture"))
    panel.find_requested.connect(lambda: events.append("find"))
    panel.save_requested.connect(lambda pin: events.append(pin))
    try:
        panel.show()
        assert not panel.note_editor.isVisible()
        QTest.mouseClick(panel.capture_button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.find_button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.note_button, Qt.MouseButton.LeftButton)
        assert panel.note_editor.isVisible()
        panel.note_editor.setPlainText("First clue\nSecond clue")
        QTest.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.pin_button, Qt.MouseButton.LeftButton)
        assert events == ["capture", "find", False, True]
        panel.note_editor.setFocus()
        QTest.keyClick(panel.note_editor, Qt.Key.Key_Escape)
        assert not panel.isVisible()
        assert panel.note_editor.toPlainText() == "First clue\nSecond clue"
    finally:
        panel.close()
        panel.deleteLater()


def test_owner_destruction_also_destroys_the_tool_window(qt_application):
    owner = QWidget()
    panel = QuickPanel(owner)
    panel.show()
    assert panel.isWindow() and panel.parentWidget() is owner
    owner.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(panel)


def test_styled_panel_collapses_and_buttons_fit_at_320_pixels(qt_application):
    panel = QuickPanel()
    panel.setStyleSheet(STYLESHEET)
    try:
        panel.resize(320, panel.sizeHint().height())
        panel.show()
        qt_application.processEvents()
        compact_height = panel.height()
        panel.note_button.click()
        qt_application.processEvents()
        assert panel.height() > compact_height
        panel.note_button.click()
        qt_application.processEvents()
        assert panel.height() == compact_height
        for button in (panel.capture_button, panel.note_button, panel.find_button):
            assert button.width() >= button.sizeHint().width()
    finally:
        panel.close()
        panel.deleteLater()


def test_long_profile_does_not_expand_the_compact_window(qt_application):
    panel = QuickPanel()
    title = "An extremely long game profile " * 12
    try:
        panel.set_game(title)
        panel.resize(340, panel.sizeHint().height())
        panel.show()
        qt_application.processEvents()
        assert panel.width() == 340
        assert panel.game_label.toolTip() == title.strip()
        assert panel.game_label.accessibleName() == f"Game: {title.strip()}"
        assert panel.game_label.text() != title.strip()
        for control in (panel.capture_button, panel.note_button, panel.find_button,
                        panel.full_panel_button):
            assert control.accessibleName()
            assert control.focusPolicy() != Qt.FocusPolicy.NoFocus
    finally:
        panel.close()
        panel.deleteLater()
