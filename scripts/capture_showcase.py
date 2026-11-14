"""Capture the real Windows UI with disposable settings and fictional sample cards."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.hint_cards import HintContent
from gaming_buddy.image_annotation import AnnotationDialog, AnnotationTool
from gaming_buddy.models import Card, CardKind
from gaming_buddy.paths import asset_path
from gaming_buddy.shortcut_dialog import ShortcutDialog
from gaming_buddy.storage import CardStore
from gaming_buddy.theme import STYLESHEET


def sample_map(path: Path) -> None:
    image = QImage(1280, 720, QImage.Format.Format_RGB32)
    image.fill(QColor("#101b2b"))
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#e3ecfa"))
        painter.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        painter.drawText(64, 86, "OBSERVATORY ACCESS")
        painter.setFont(QFont("Segoe UI", 16))
        painter.setPen(QColor("#99b1cc"))
        painter.drawText(64, 126, "Fictional clue diagram · sample content")
        painter.setPen(QPen(QColor("#43617d"), 18))
        painter.drawLine(270, 360, 970, 360)
        for x, title, subtitle in (
            (80, "LIFT", "Starting point"),
            (480, "ARCHIVE", "Find the brass key"),
            (880, "NORTH DOOR", "Access code: 0451"),
        ):
            painter.setPen(QPen(QColor("#688cb1"), 2))
            painter.setBrush(QColor("#192b42"))
            painter.drawRoundedRect(QRectF(x, 250, 300, 220), 18, 18)
            painter.setPen(QColor("#edf5ff"))
            painter.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
            painter.drawText(x + 24, 320, title)
            painter.setPen(QColor("#abc1da"))
            painter.setFont(QFont("Segoe UI", 15))
            painter.drawText(x + 24, 365, subtitle)
        painter.setPen(QColor("#99b1cc"))
        painter.drawText(
            64, 640, "Keep the clue beside your notes. Return after the next checkpoint."
        )
    finally:
        painter.end()
    if not image.save(str(path), "PNG"):
        raise OSError("Could not save the synthetic clue diagram.")


def capture_showcase(workspace: Path, output: Path) -> dict:
    workspace, output = workspace.resolve(), output.resolve()
    if workspace.exists() or output.exists():
        raise ValueError(
            "Use new workspace and output directories; existing files are never replaced."
        )
    if workspace.is_relative_to(output) or output.is_relative_to(workspace):
        raise ValueError("Keep the disposable workspace separate from the published images.")
    workspace.mkdir(parents=True)
    output.mkdir(parents=True)
    captures = workspace / "captures"
    captures.mkdir()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(str(asset_path("app-icon.png"))))
    if app.platformName() != "windows":
        raise RuntimeError("Use the native Windows Qt backend for these screenshots.")
    native_settings = QSettings("GamingBuddy", "GamingBuddy")
    settings_before = {key: native_settings.value(key) for key in native_settings.allKeys()}
    settings = QSettings(str(workspace / "settings.ini"), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    for key, value in {
        "onboarding/completed": True,
        "updates/automatic_checks": False,
        "preview/visible": True,
        "game": "Starfall Expedition",
    }.items():
        settings.setValue(key, value)
    clue = captures / "observatory-clue.png"
    sample_map(clue)
    images = []

    def save(widget: QWidget, name: str) -> None:
        widget.show()
        widget.raise_()
        QTest.qWait(180)
        pixmap = widget.grab()
        target = output / name
        if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
            raise OSError(f"Could not capture {name}.")
        images.append(
            {
                "file": name,
                "width": pixmap.width(),
                "height": pixmap.height(),
                "device_pixel_ratio": pixmap.devicePixelRatio(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )

    with CardStore(workspace / "cards.sqlite3") as store:
        note = store.add(
            Card(
                None,
                CardKind.NOTE,
                "Starfall Expedition",
                "Observatory route",
                "# Observatory route\n\nKeep this route ready for the next session.\n\n"
                "## Before you leave\n- [x] Find the brass key in the archive\n"
                "- [ ] Open the north door\n- [ ] Return to the lift\n\n"
                "**Door code:** `0451`\n\n> Check the balcony before leaving the observatory.",
                tags=("route", "checklist"),
                favorite=True,
                width=420,
                height=360,
            )
        )
        image_card = store.add(
            Card(
                None,
                CardKind.IMAGE,
                "Starfall Expedition",
                "Observatory access map",
                "North door: 0451. Find the brass key in the archive.",
                str(clue),
                tags=("map", "code"),
                favorite=True,
            )
        )
        hint = store.add(
            Card(
                None,
                CardKind.NOTE,
                "Starfall Expedition",
                "Three-symbol gate",
                tags=("puzzle",),
                width=420,
                height=300,
                hints=HintContent(
                    (
                        "Look for a repeated **symbol** near the gate.",
                        "Compare the three symbols on the wall with the wheels.",
                        "Turn the wheels to sun, moon, star, then press the centre switch.",
                    )
                ),
            )
        )
        store.add(
            Card(
                None,
                CardKind.NOTE,
                "Arena practice",
                "Support build",
                "Prioritise cooldowns. Save the team shield for the final phase.",
                tags=("build",),
            )
        )
        panel = None
        auxiliary = []
        with patch.object(dashboard_module, "QSettings", lambda *_: settings):
            try:
                panel = Dashboard(store, captures)
                for timer in panel._startup_timers:
                    timer.stop()
                panel.game_detector.stop()
                panel.resize(1120, 800)
                panel.main_tabs.setCurrentIndex(2)

                def select_card(card: Card) -> None:
                    for row in range(panel.card_list.count()):
                        item = panel.card_list.item(row)
                        if item.data(Qt.ItemDataRole.UserRole) == card.id:
                            panel.card_list.setCurrentItem(item)
                            return
                    raise RuntimeError("Sample card is missing from the visible library.")

                select_card(note)
                save(panel, "library.png")
                select_card(image_card)
                save(panel, "capture-library.png")
                panel.hide()

                for card, filename in ((note, "pinned-note.png"), (hint, "hint-card.png")):
                    panel.show_pin(card, persist=False)
                    pin = panel.pins[card.id]
                    if card.hints:
                        pin.hint_view.reveal_button.click()
                        if pin.hint_view.hints.revealed != 1:
                            raise RuntimeError("Hint progress did not update.")
                        if "sun, moon, star" in pin.hint_view.content.toPlainText():
                            raise RuntimeError("Unrevealed solution appeared in the hint view.")
                    save(pin, filename)
                    pin.hide()

                panel.show_quick_panel()
                quick = panel.quick_panel.panel
                if quick is None:
                    raise RuntimeError("The connected quick panel did not open.")
                quick.resize(420, quick.height())
                quick.note_button.setChecked(True)
                quick.note_editor.setPlainText(
                    "Balcony clue\n\nThe north door uses code 0451.\nReturn after the next checkpoint."
                )
                save(quick, "quick-panel.png")
                quick.save_button.click()
                if not any(card.title == "Balcony clue" for card in store.list()):
                    raise RuntimeError("Quick panel note was not saved in the isolated library.")
                quick.hide()

                panel.show_quick_finder()
                finder = panel._quick_finder
                finder.search.setText("observatory")
                save(finder, "quick-finder.png")
                finder.hide()

                annotation = AnnotationDialog(clue)
                auxiliary.append(annotation)
                annotation.resize(1000, 680)
                annotation.canvas.document.add_arrow(
                    QPointF(620, 500), QPointF(1000, 430), QColor("#aa88ff"), 7
                )
                annotation.canvas.state_changed.emit()
                annotation.tool_buttons[AnnotationTool.ARROW].click()
                annotation.canvas.update()
                save(annotation, "screenshot-annotation.png")
                annotation.hide()

                shortcuts = ShortcutDialog(panel.shortcuts)
                auxiliary.append(shortcuts)
                save(shortcuts, "keyboard-shortcuts.png")
            finally:
                for widget in auxiliary:
                    widget.hide()
                    widget.deleteLater()
                if panel is not None:
                    panel._quitting = True
                    panel.note_draft_timer.stop()
                    for pin in panel.pins.values():
                        pin.discard_pending_layout()
                        pin.close()
                        pin.deleteLater()
                    panel.pins.clear()
                    panel.tray.hide()
                    panel._really_quit = True
                    panel.close()
                    panel.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    settings.sync()
    native_settings.sync()
    if settings_before != {key: native_settings.value(key) for key in native_settings.allKeys()}:
        raise RuntimeError("Native user settings changed during the capture.")
    return {
        "qt_platform": app.platformName(),
        "os": platform.platform(),
        "content": "fictional sample cards and a code-drawn clue diagram",
        "capture_method": "unmodified application widgets; QWidget.grab; lossless PNG",
        "native_user_settings": "unchanged",
        "installer_acceptance": "not tested",
        "images": images,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture_showcase(args.workspace, args.output)
    (args.workspace / "capture-report.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
