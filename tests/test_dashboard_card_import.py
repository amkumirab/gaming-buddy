from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import gaming_buddy.dashboard as dashboard_module
from gaming_buddy.card_export import create_card_export
from gaming_buddy.card_pack_dialog import CardPackDialog
from gaming_buddy.dashboard import Dashboard
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.fixture
def panel(tmp_path, monkeypatch, qt_application):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("onboarding/completed", True)
    settings.setValue("updates/automatic_checks", False)
    monkeypatch.setattr(dashboard_module, "QSettings", lambda *_: settings)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        store.add(Card(None, CardKind.NOTE, "Original", "Keep", content="Untouched"))
        window = Dashboard(store, tmp_path / "captures")
        yield window
        window.note_draft_timer.stop()
        window.game_detector.stop()
        window.tray.hide()
        window._really_quit = True
        window.close()
        window.deleteLater()
        qt_application.processEvents()


def prepare_pack(tmp_path, monkeypatch):
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("purple"))
    path = tmp_path / "map.png"
    assert image.save(str(path))
    archive = tmp_path / "cards.zip"
    create_card_export(archive, [
        Card(None, CardKind.NOTE, "Puzzle", "Clue", content="First\n\nSecond\n"),
        Card(None, CardKind.IMAGE, "Puzzle", "Map", image_path=str(path)),
    ])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(archive), ""))
    return path


def automate_dialog(monkeypatch, *, cancel=False, before_return=None):
    class Preview(CardPackDialog):
        def exec(self):
            timer = QTimer(self)
            timer.setInterval(10)

            def proceed():
                if cancel or self.import_button.isEnabled():
                    timer.stop()
                    self.reject() if cancel else self.accept()

            timer.timeout.connect(proceed)
            watchdog = QTimer(self)
            watchdog.setSingleShot(True)
            watchdog.timeout.connect(self.reject)
            timer.start()
            watchdog.start(5000)
            try:
                result = super().exec()
                if before_return:
                    before_return()
                return result
            finally:
                timer.stop()
                watchdog.stop()

    monkeypatch.setattr(dashboard_module, "CardPackDialog", Preview)


def test_import_round_trip_skips_duplicates_and_keeps_workspace(panel, tmp_path, monkeypatch):
    original = panel.store.list()[0]
    path = prepare_pack(tmp_path, monkeypatch)
    automate_dialog(monkeypatch)
    panel.game_input.setText("Original")
    panel.search_cards.setText("Keep")
    panel.filter_current.setChecked(True)
    paused, resumed = [], []
    panel.shortcut_editing_started.connect(lambda: paused.append(True))
    panel.shortcut_editing_cancelled.connect(lambda: resumed.append(True))
    panel.import_card_pack()
    assert len(panel.store.list()) == 3
    assert panel.store.get(original.id) == original
    assert panel.game_input.text() == "Original"
    assert panel.search_cards.text() == "Keep"
    assert panel.filter_current.isChecked()
    assert not panel.pins
    imported_image = next(card for card in panel.store.list() if card.kind is CardKind.IMAGE)
    assert Path(imported_image.image_path).read_bytes() == path.read_bytes()
    panel.import_card_pack()
    assert len(panel.store.list()) == 3
    assert "2 duplicate(s)" in panel.statusBar().currentMessage()
    assert len(list(panel.captures_dir.iterdir())) == 1
    assert paused == resumed == [True, True]
    assert panel._card_pack_dialog is None


def test_cancel_import_does_not_write(panel, tmp_path, monkeypatch):
    prepare_pack(tmp_path, monkeypatch)
    automate_dialog(monkeypatch, cancel=True)
    panel.import_card_pack()
    assert len(panel.store.list()) == 1
    assert not panel.captures_dir.exists()


def test_quit_after_preview_prevents_commit(panel, tmp_path, monkeypatch):
    prepare_pack(tmp_path, monkeypatch)
    automate_dialog(monkeypatch, before_return=lambda: setattr(panel, "_quitting", True))
    panel.import_card_pack()
    assert len(panel.store.list()) == 1
    assert not panel.captures_dir.exists()


def test_database_failure_removes_only_new_copies(panel, tmp_path, monkeypatch):
    prepare_pack(tmp_path, monkeypatch)
    automate_dialog(monkeypatch)
    panel.store._connection.execute(
        "CREATE TRIGGER reject_pack BEFORE INSERT ON cards BEGIN SELECT RAISE(ABORT,'test'); END"
    )
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    panel.import_card_pack()
    assert warnings
    assert len(panel.store.list()) == 1
    assert not list(panel.captures_dir.glob("pack-*"))


def test_refresh_failure_after_commit_preserves_saved_images(panel, tmp_path, monkeypatch):
    prepare_pack(tmp_path, monkeypatch)
    automate_dialog(monkeypatch)
    monkeypatch.setattr(panel, "refresh_cards", lambda: (_ for _ in ()).throw(OSError("refresh")))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    panel.import_card_pack()
    assert len(panel.store.list()) == 3
    assert len(list(panel.captures_dir.glob("pack-*"))) == 1
    assert warnings and "saved" in warnings[0][2].lower()


def test_capture_in_progress_does_not_open_import(panel, monkeypatch):
    opens = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: opens.append(True))
    panel._capture_in_progress = True
    panel.import_card_pack()
    assert not opens


def test_queued_capture_shortcuts_are_blocked_during_pack_preview(panel, monkeypatch):
    panel._card_pack_dialog = object()
    monkeypatch.setattr(dashboard_module, "grab_monitor", lambda *a: pytest.fail("Captured during preview"))
    try:
        panel.start_capture()
        assert not panel._capture_in_progress
        panel.start_full_screen_capture()
        assert not panel._capture_in_progress
    finally:
        panel._capture_timer.stop()
        panel._capture_in_progress = False
        panel._card_pack_dialog = None


def test_shutdown_waits_for_pack_reader_and_does_not_import(panel, tmp_path, monkeypatch):
    from gaming_buddy.card_pack import CardPack, PackCard

    entered, release = threading.Event(), threading.Event()
    exits, observed = [], []

    def slow_reader(*args, **kwargs):
        entered.set()
        release.wait(5)
        return CardPack((PackCard(CardKind.NOTE, "Game", "Late", "", (), False, ""),))

    monkeypatch.setattr("gaming_buddy.card_pack_dialog.load_card_pack", slow_reader)
    monkeypatch.setattr(QApplication, "quit", lambda: exits.append(True))
    prepare_pack(tmp_path, monkeypatch)
    timer = QTimer(panel)
    timer.setInterval(10)

    def request_close():
        if entered.is_set():
            timer.stop()
            panel.quit_app()
            observed.append(not panel._background_tasks_finished())
            observed.append(len(panel.store.list()) == 1)
            release.set()

    timer.timeout.connect(request_close)
    timer.start()
    try:
        panel.import_card_pack()
        deadline = time.monotonic() + 3
        while not exits and time.monotonic() < deadline:
            QTest.qWait(10)
        assert exits == [True]
        assert observed == [True, True]
        assert len(panel.store.list()) == 1
        assert not panel.captures_dir.exists()
    finally:
        release.set()
        timer.stop()
