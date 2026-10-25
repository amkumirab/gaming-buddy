"""Map native Markdown task markers to exact source characters, without serialization."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from PySide6.QtGui import QTextBlock, QTextBlockFormat, QTextDocument

_TASK = re.compile(
    r"(?m)^[ \t]*(?:[-+*]|\d+[.)])[ \t]+\[(?P<state>[ xX])\][ \t]+"
)


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    offset: int
    checked: bool
    block: QTextBlock


def checklist_items(source: str, document: QTextDocument) -> tuple[ChecklistItem, ...]:
    """Let Qt recognize lists/code; temporary labels retain unambiguous source positions."""
    tokens: list[tuple[str, int]] = []
    nonce = uuid.uuid4().hex

    def annotate(match: re.Match[str]) -> str:
        token = f"gbtask{nonce}n{len(tokens)}end"
        tokens.append((token, match.start("state")))
        return match.group() + token

    document.setMarkdown(_TASK.sub(annotate, source))
    items = []
    for token, offset in tokens:
        cursor = document.find(token)
        if cursor.isNull():
            continue
        block = cursor.block()
        if (block.textList() is not None and block.text().startswith(token)
                and block.blockFormat().marker() in (
                    QTextBlockFormat.MarkerType.Unchecked, QTextBlockFormat.MarkerType.Checked,
                )):
            items.append(ChecklistItem(offset, source[offset] != " ", block))
        cursor.removeSelectedText()
    return tuple(items)


def set_task(source: str, offset: int, checked: bool) -> str:
    if (type(offset) is not int or not 1 <= offset < len(source) - 1
            or source[offset - 1:offset] != "[" or source[offset + 1:offset + 2] != "]"
            or source[offset] not in " xX" or type(checked) is not bool):
        raise ValueError("Invalid checklist marker.")
    return source[:offset] + ("x" if checked else " ") + source[offset + 1:]
