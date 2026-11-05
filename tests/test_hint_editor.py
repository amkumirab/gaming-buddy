from gaming_buddy.hint_editor import HintEditor
from gaming_buddy.models import Card, CardKind


def test_hint_editor_requires_three_stages_and_keeps_multiline_source(qt_application):
    editor = HintEditor(Card(None, CardKind.NOTE, "Game", "Guide"))
    editor.accept()
    assert editor.result() == 0 and not editor.error.isHidden()
    for field, text in zip(editor.steps, ("First\n\n  clue\n", "Next", "Answer"), strict=True):
        field.setPlainText(text)
    editor.accept()
    assert editor.result() == 1
    assert editor.hint_content().steps[0] == "First\n\n  clue\n"
    editor.deleteLater()
