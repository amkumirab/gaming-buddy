import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest

from gaming_buddy.theme import STYLESHEET
from gaming_buddy.walkthrough import WalkthroughPanel, WalkthroughProgress


def test_progress_round_trip_and_skip_are_distinct_from_completion(tmp_path):
    path = str(tmp_path / "settings.ini")
    settings = QSettings(path, QSettings.Format.IniFormat)
    progress = WalkthroughProgress.load(settings)
    assert progress.step == 0 and progress.paused
    progress.paused = False
    progress.note_id = 42
    progress.advance()
    progress.advance(skip=True)
    progress.save(settings)
    restored = WalkthroughProgress.load(QSettings(path, QSettings.Format.IniFormat))
    assert restored == progress
    assert restored.step == 2 and restored.skipped == (1,)
    restored.advance()
    restored.advance()
    restored.advance(skip=True)
    assert restored.step == 4 and restored.skipped == (1,)


@pytest.mark.parametrize("step", [-1, 9, "broken", None])
def test_invalid_saved_progress_starts_safely(tmp_path, step):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/walkthrough/step", step)
    settings.setValue("onboarding/walkthrough/skipped", ["bad", "50", "-1"])
    settings.setValue("onboarding/walkthrough/note_id", "bad")
    progress = WalkthroughProgress.load(settings)
    assert progress.step == 0 and progress.note_id is None and progress.skipped == ()


def test_panel_keyboard_actions_and_wrapping_plain_text(qt_application):
    panel = WalkthroughPanel()
    events = []
    panel.action_requested.connect(lambda: events.append("act"))
    panel.skip_requested.connect(lambda: events.append("skip"))
    panel.pause_requested.connect(lambda: events.append("pause"))
    panel.set_step(0, "Write a clue", "Your existing draft stays here.", "Write note")
    panel.resize(390, panel.sizeHint().height())
    panel.show()
    for button, event in [(panel.action_button, "act"), (panel.skip_button, "skip"),
                          (panel.pause_button, "pause")]:
        button.setFocus()
        QTest.keyClick(button, Qt.Key.Key_Space)
        assert events[-1] == event
        assert button.accessibleName()
    assert panel.description.wordWrap()
    assert panel.description.textFormat() == Qt.TextFormat.PlainText
    panel.set_step(4, "You're ready", "3 completed; 1 skipped.", "Restart")
    assert not panel.skip_button.isVisible()
    assert panel.pause_button.text() == "Finish"
    panel.close()
    panel.deleteLater()


def test_themed_step_card_fits_small_window_and_keyboard_tab_order(qt_application):
    panel = WalkthroughPanel()
    panel.setStyleSheet(STYLESHEET)
    panel.set_step(2, "Capture a clue", "Capture a clue. " * 16, "Capture")
    panel.resize(398, panel.sizeHint().height())
    panel.show()
    qt_application.processEvents()
    qt_application.processEvents()
    assert panel.description.height() >= panel.description.heightForWidth(panel.description.width())
    for button in (panel.action_button, panel.skip_button, panel.pause_button, panel.reference_button):
        assert button.width() >= button.sizeHint().width()
    panel.action_button.setFocus()
    QTest.keyClick(panel.action_button, Qt.Key.Key_Tab)
    assert panel.focusWidget() is panel.skip_button
    QTest.keyClick(panel.skip_button, Qt.Key.Key_Tab)
    assert panel.focusWidget() is panel.pause_button
    panel.close()
    panel.deleteLater()
