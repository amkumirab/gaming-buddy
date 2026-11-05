from PySide6.QtWidgets import QMessageBox

from gaming_buddy.hint_cards import HintContent
from gaming_buddy.hint_view import HintView


def test_reveal_is_sequential_and_solution_needs_confirmation(qt_application, monkeypatch):
    calls = []

    def save(expected, target):
        calls.append((expected, target))
        return expected.with_progress(target)

    view = HintView(save)
    hints = HintContent(("SUBTLE", "GUIDANCE", "SECRET-0451"))
    view.set_hints(hints)
    assert all(step not in view.content.toPlainText() for step in hints.steps)
    view.reveal_button.click()
    assert "SUBTLE" in view.content.toPlainText()
    assert "GUIDANCE" not in view.content.toPlainText()
    view.reveal_button.click()
    assert "GUIDANCE" in view.content.toPlainText()
    assert "SECRET-0451" not in view.content.toPlainText()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    view.reveal_button.click()
    assert len(calls) == 2 and view.hints.revealed == 2
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    view.reveal_button.click()
    assert len(calls) == 3 and "SECRET-0451" in view.content.toPlainText()
    assert not view.reveal_button.isEnabled()
    view.reset_button.click()
    assert view.hints.revealed == 0 and "SECRET-0451" not in view.content.toPlainText()
    view.deleteLater()


def test_failed_save_and_stale_modal_do_not_reveal_hidden_text(qt_application, monkeypatch):
    view = HintView(lambda *_: None)
    hints = HintContent(("A", "B", "SECRET"), 2)
    view.set_hints(hints)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    view.reveal_button.click()
    assert view.hints == hints and "SECRET" not in view.content.toPlainText()
    assert "not saved" in view.status.text()

    def replace_during_confirmation(*_):
        view.set_hints(HintContent(("New", "Other", "NEW-SECRET")))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", replace_during_confirmation)
    view.reveal_button.click()
    assert view.hints.revealed == 0
    assert "NEW-SECRET" not in view.content.toPlainText()
    view.deleteLater()


def test_switching_to_an_identical_guide_during_confirmation_cancels_reveal(qt_application,
                                                                        monkeypatch):
    saves = []
    view = HintView(lambda *args: saves.append(args))
    hints = HintContent(("a", "b", "c"), 2)
    view.set_hints(hints)

    def switch(*_):
        view.set_hints(hints)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", switch)
    view.reveal_button.click()
    assert saves == [] and view.hints.revealed == 2
    view.deleteLater()
