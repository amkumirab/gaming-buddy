from __future__ import annotations

import pytest
from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication

from gaming_buddy.markdown_view import MarkdownPreview, contains_markdown


@pytest.fixture(scope="module")
def application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        assert isinstance(existing, QApplication)
        return existing
    return QApplication([])


def test_markdown_preview_renders_common_formatting(application: QApplication) -> None:
    preview = MarkdownPreview()

    preview.set_markdown("# Route\n\n- Turn **left**\n- Enter `0421`")

    assert preview.toPlainText() == "Route\nTurn left\nEnter 0421"
    assert "font-weight:700" in preview.toHtml().replace(" ", "")
    preview.close()


def test_plain_multiline_notes_keep_their_line_breaks(application: QApplication) -> None:
    source = "First objective\nSecond objective\n\nSafe code: 0421"
    preview = MarkdownPreview()

    preview.set_markdown(source)

    assert not contains_markdown(source)
    assert preview.toPlainText() == source
    preview.close()


@pytest.mark.parametrize(
    "source",
    [
        "https://example.com/tracker.png",
        "file:///C:/Users/Player/secret.png",
    ],
)
def test_markdown_preview_blocks_image_resources(
    application: QApplication,
    source: str,
) -> None:
    preview = MarkdownPreview()

    result = preview.loadResource(
        QTextDocument.ResourceType.ImageResource,
        QUrl(source),
    )

    assert isinstance(result, QByteArray)
    assert result.isEmpty()
    assert not preview.openLinks()
    assert not preview.openExternalLinks()
    preview.close()
