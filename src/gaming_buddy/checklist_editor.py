"""Insert task lines using Qt cursor positions, including non-BMP Unicode text."""

from __future__ import annotations

import re

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit

_BULLET = re.compile(r"^(?P<indent>[ \t]*)(?:[-+*]|\d+[.)])[ \t]+")
_EXISTING_TASK = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+\[[ xX]\](?:[ \t]+|$)")


def insert_checklist(editor: QTextEdit) -> None:
    cursor = editor.textCursor()
    selected = cursor.hasSelection()
    start, end = cursor.selectionStart(), cursor.selectionEnd()
    first = editor.document().findBlock(start)
    last = editor.document().findBlock(max(start, end - 1) if selected else end)
    cursor.setPosition(first.position())
    cursor.setPosition(last.position() + last.length() - 1, QTextCursor.MoveMode.KeepAnchor)
    original = cursor.selectedText().replace("\u2029", "\n")
    lines = []
    for line in original.split("\n"):
        if _EXISTING_TASK.match(line) or (not line.strip() and selected):
            lines.append(line)
        elif _BULLET.match(line):
            lines.append(_BULLET.sub(r"\g<indent>- [ ] ", line, count=1))
        else:
            indent = len(line) - len(line.lstrip(" \t"))
            lines.append(line[:indent] + "- [ ] " + line[indent:])
    replacement = "\n".join(lines)
    if replacement != original:
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        if selected:
            end_position = cursor.position()
            cursor.setPosition(first.position())
            cursor.setPosition(end_position, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
    editor.setFocus()
