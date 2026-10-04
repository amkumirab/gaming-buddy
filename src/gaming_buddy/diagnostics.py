from __future__ import annotations

import platform
import sqlite3
import sys
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import qVersion
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QSystemTrayIcon

from gaming_buddy import __version__


class IssueKind(Enum):
    SHORTCUTS = "Global shortcut listener failed"
    CAPTURE = "Screenshot capture or saving failed"
    IMPORT = "Image import failed"
    DRAFT = "Note draft saving failed"
    NOTE = "Note saving failed"
    UPDATE_CHECK = "Update check failed"
    UPDATE_DOWNLOAD = "Update download failed"


@dataclass(frozen=True, slots=True)
class RecentIssue:
    kind: IssueKind
    occurred_at: datetime


class DiagnosticHistory:
    """Keep fixed error categories in memory, never exception text or user content."""

    def __init__(self) -> None:
        self._issues: deque[RecentIssue] = deque(maxlen=5)

    def record(self, kind: IssueKind) -> None:
        if not isinstance(kind, IssueKind):
            raise TypeError("A known diagnostic category is required.")
        self._issues.append(RecentIssue(kind, datetime.now(UTC)))

    def snapshot(self) -> tuple[RecentIssue, ...]:
        return tuple(self._issues)


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    environment: tuple[str, ...]
    checks: tuple[DiagnosticCheck, ...]
    recent_issues: tuple[RecentIssue, ...] = ()

    def as_text(self) -> str:
        lines = ["Gaming Buddy diagnostic report", *self.environment, "", "Checks"]
        for check in self.checks:
            lines.extend((f"{check.name}: {check.status}", f"  {check.detail}"))
        lines.extend(("", "Recent errors (current session only)"))
        for issue in self.recent_issues:
            timestamp = issue.occurred_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            lines.append(f"- {timestamp}: {issue.kind.value}")
        if not self.recent_issues:
            lines.append("No tracked errors in this session.")
        lines.extend(
            (
                "",
                "This report excludes notes, images, game names, file paths, account names,",
                "raw error messages, and keyboard input. It is not uploaded automatically.",
                "Checks do not verify in-game capture, existing database integrity, or",
                "shortcut conflicts with another application.",
            )
        )
        return "\n".join(lines)


def _storage_check(folder: Path, *, image: bool) -> DiagnosticCheck:
    name = "Screenshot folder (PNG)" if image else "Notes folder (SQLite)"
    try:
        with TemporaryDirectory(prefix=".gaming-buddy-check-", dir=folder) as temporary:
            scratch = Path(temporary)
            if image:
                sample = QImage(2, 2, QImage.Format.Format_RGB32)
                sample.fill(0xFF7C5CFF)
                if not sample.save(str(scratch / "sample.png"), "PNG"):
                    return DiagnosticCheck(
                        name, "Needs attention", "PNG encoding failed. Restart the app."
                    )
            else:
                connection = sqlite3.connect(scratch / "sample.sqlite3")
                try:
                    connection.execute("CREATE TABLE probe (value INTEGER)")
                    connection.execute("INSERT INTO probe VALUES (1)")
                    connection.commit()
                finally:
                    connection.close()
        return DiagnosticCheck(name, "Ready", "A temporary write succeeded and was cleaned up.")
    except PermissionError:
        detail = "Allow write access to the local data folder, then run checks again."
    except FileNotFoundError:
        detail = "The local data folder is missing. Restart the app to recreate it."
    except (OSError, sqlite3.Error):
        detail = "Check free disk space and folder access, then run checks again."
    return DiagnosticCheck(name, "Needs attention", detail)


def collect_diagnostics(
    storage_path: Path,
    captures_path: Path,
    *,
    shortcuts_running: bool | None = None,
    shortcuts_paused: bool = False,
    tray_visible: bool | None = None,
    recent_issues: tuple[RecentIssue, ...] = (),
    version: str = __version__,
) -> DiagnosticReport:
    if shortcuts_running is None:
        shortcuts = DiagnosticCheck(
            "Global shortcuts", "Unknown", "Listener status is not available."
        )
    elif not shortcuts_running:
        shortcuts = DiagnosticCheck(
            "Global shortcuts",
            "Needs attention",
            "The listener was not running. Close Settings and restart the app if shortcuts fail.",
        )
    elif shortcuts_paused:
        shortcuts = DiagnosticCheck(
            "Global shortcuts",
            "Paused in Settings",
            "The listener was running before Settings opened. Close Settings to resume it.",
        )
    else:
        shortcuts = DiagnosticCheck(
            "Global shortcuts", "Running", "The keyboard listener is alive."
        )

    if not QSystemTrayIcon.isSystemTrayAvailable():
        tray = DiagnosticCheck(
            "System tray",
            "Needs attention",
            "Windows tray is unavailable. Keep the panel open and restart Windows Explorer if needed.",
        )
    elif tray_visible is False:
        tray = DiagnosticCheck(
            "System tray", "Needs attention", "The tray icon is not enabled. Restart the app."
        )
    elif tray_visible is None:
        tray = DiagnosticCheck(
            "System tray", "Unknown", "Tray is available; app icon status is unknown."
        )
    else:
        tray = DiagnosticCheck(
            "System tray",
            "Ready",
            "The icon is enabled. Check hidden tray icons if it is not visible on the taskbar.",
        )

    screens = QGuiApplication.screens() if QGuiApplication.instance() is not None else []
    display_lines = tuple(
        f"Display {index}: {screen.size().width()} x {screen.size().height()} logical pixels; "
        f"scale {screen.devicePixelRatio():g}x"
        for index, screen in enumerate(screens, 1)
    )
    return DiagnosticReport(
        environment=(
            f"App version: {version}",
            f"Operating system: {platform.system()} {platform.release()} ({platform.version()})",
            f"Architecture: {platform.machine()}",
            f"Runtime: Python {platform.python_version()}; Qt {qVersion()}",
            f"Build type: {'Installed bundle' if getattr(sys, 'frozen', False) else 'Source run'}",
            f"Connected displays: {len(screens)}",
            *display_lines,
        ),
        checks=(
            _storage_check(storage_path, image=False),
            _storage_check(captures_path, image=True),
            tray,
            shortcuts,
        ),
        recent_issues=recent_issues,
    )
