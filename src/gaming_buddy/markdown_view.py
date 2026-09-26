from __future__ import annotations

import re

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QTextBrowser, QWidget

_BLOCK_MARKDOWN = re.compile(
    r"(?m)^(?: {0,3}(?:#{1,6}\s|>|[-+*]\s|\d+[.)]\s|```|~~~)| {4}\S)"
)
_INLINE_MARKDOWN = re.compile(
    r"(?:\*\*[^*\n]+\*\*|__[^_\n]+__|(?<!\*)\*[^*\n]+\*(?!\*)|"
    r"(?<!_)_[^_\n]+_(?!_)|`[^`\n]+`|!?\[[^]\n]+\]\([^)\n]+\))"
)


def contains_markdown(source: str) -> bool:
    return bool(_BLOCK_MARKDOWN.search(source) or _INLINE_MARKDOWN.search(source))


class MarkdownPreview(QTextBrowser):
    """Read-only Markdown rendering without loading linked image resources."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)

    def set_markdown(self, source: str) -> None:
        if contains_markdown(source):
            self.setMarkdown(source)
        else:
            self.setPlainText(source)

    def loadResource(
        self,
        resource_type: int,
        name: QUrl,
    ) -> object:
        if resource_type == QTextDocument.ResourceType.ImageResource:
            return QByteArray()
        return super().loadResource(resource_type, name)
