from __future__ import annotations

import threading
import time

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from gaming_buddy.card_pack import CardPack, PackCard
from gaming_buddy.card_pack_dialog import CardPackDialog
from gaming_buddy.models import CardKind


def wait_until(predicate, timeout=5000):
    deadline = time.monotonic() + timeout / 1000
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


def pack():
    return CardPack((
        PackCard(CardKind.NOTE, "Adventure", "<b>Route</b>", "a\n\nb\n", (), False, ""),
        PackCard(CardKind.IMAGE, "Adventure", "Missing map", "", (), False, ""),
    ))


def dialog(tmp_path, monkeypatch, loader=None):
    monkeypatch.setattr("gaming_buddy.card_pack_dialog.load_card_pack",
                        loader or (lambda *args, **kwargs: pack()))
    window = CardPackDialog(tmp_path / "cards.zip", [], tmp_path / "captures", ["Puzzle"])
    window.show()
    return window


def test_preview_selection_and_destination_are_read_only(tmp_path, monkeypatch):
    window = dialog(tmp_path, monkeypatch)
    try:
        wait_until(lambda: window.card_list.count() == 2)
        assert window.selected_indices() == [0]
        assert not window.card_list.item(1).flags() & Qt.ItemFlag.ItemIsUserCheckable
        assert window.note_preview.toPlainText() == "a\n\nb\n"
        assert window.preview_title.textFormat() == Qt.TextFormat.PlainText
        assert window.preview_title.text() == "<b>Route</b>"
        window.use_game.setChecked(True)
        window.game_input.setCurrentText("Puzzle")
        window.accept()
        wait_until(lambda: window.result() == QDialog.DialogCode.Accepted)
        assert window.plan.cards[0].game == "Puzzle"
        assert not (tmp_path / "captures").exists()
    finally:
        window.reject()
        window.deleteLater()


def test_clear_selection_disables_import(tmp_path, monkeypatch):
    window = dialog(tmp_path, monkeypatch)
    try:
        wait_until(lambda: window.card_list.count() == 2)
        window.clear_button.click()
        assert not window.import_button.isEnabled()
        window.select_button.click()
        assert window.selected_indices() == [0]
    finally:
        window.reject()
        window.deleteLater()


@pytest.mark.parametrize("cancel", ["reject", "escape", "close"])
def test_slow_reader_keeps_gui_alive_and_cancel_waits_for_thread(tmp_path, monkeypatch, cancel):
    entered, release = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        entered.set()
        release.wait(5)
        return pack()

    window = dialog(tmp_path, monkeypatch, slow)
    beats = []
    timer = QTimer(window)
    timer.timeout.connect(lambda: beats.append(True))
    timer.start(5)
    try:
        wait_until(entered.is_set)
        if cancel == "escape":
            QTest.keyClick(window, Qt.Key.Key_Escape)
        elif cancel == "close":
            window.close()
        else:
            window.reject()
        assert not window.shutdown_ready
        assert window.isVisible()
        QTest.qWait(40)
        assert beats
        release.set()
        wait_until(lambda: window.shutdown_ready and not window.isVisible())
        assert window.plan is None
        assert window.card_list.count() == 0
    finally:
        release.set()
        wait_until(lambda: window.shutdown_ready)
        window.reject()
        window.deleteLater()


def test_shutdown_discards_late_plan(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        from gaming_buddy.card_pack_import import CardImportPlan
        entered.set()
        release.wait(5)
        return CardImportPlan(pack().cards[:1], 0, 0)

    window = dialog(tmp_path, monkeypatch)
    monkeypatch.setattr("gaming_buddy.card_pack_dialog.plan_card_import", slow)
    try:
        wait_until(lambda: window.import_button.isEnabled())
        window.accept()
        wait_until(entered.is_set)
        window.begin_shutdown()
        assert not window.shutdown_ready
        release.set()
        wait_until(lambda: window.shutdown_ready and not window.isVisible())
        assert window.result() == QDialog.DialogCode.Rejected
        assert window.plan is None
    finally:
        release.set()
        wait_until(lambda: window.shutdown_ready)
        window.reject()
        window.deleteLater()


def test_shutdown_before_autostart_never_starts_reader(tmp_path, monkeypatch):
    calls = []
    window = dialog(tmp_path, monkeypatch, lambda *a, **kw: calls.append(True))
    window.begin_shutdown()
    QTest.qWait(30)
    assert not calls
    assert window.shutdown_ready
    window.deleteLater()


def test_invalid_pack_shows_error_without_starting_import(tmp_path, monkeypatch):
    from gaming_buddy.card_pack import CardPackError

    def invalid(*args, **kwargs):
        raise CardPackError("Invalid card pack.")

    window = dialog(tmp_path, monkeypatch, invalid)
    try:
        wait_until(lambda: "Invalid card pack" in window.status.text())
        assert not window.import_button.isEnabled()
        assert window.shutdown_ready
        assert window.plan is None
    finally:
        window.reject()
        window.deleteLater()


def test_pack_with_only_missing_images_cannot_be_imported(tmp_path, monkeypatch):
    window = dialog(tmp_path, monkeypatch, lambda *a, **kw: CardPack(pack().cards[1:]))
    try:
        wait_until(lambda: window.card_list.count() == 1)
        window.select_button.click()
        assert window.selected_indices() == []
        assert not window.import_button.isEnabled()
        assert "1 missing image" in window.status.text()
    finally:
        window.reject()
        window.deleteLater()


def test_keyboard_space_toggles_selection(tmp_path, monkeypatch):
    window = dialog(tmp_path, monkeypatch)
    try:
        wait_until(lambda: window.import_button.isEnabled())
        window.card_list.setFocus()
        QTest.keyClick(window.card_list, Qt.Key.Key_Space)
        assert window.selected_indices() == []
        assert not window.import_button.isEnabled()
        QTest.keyClick(window.card_list, Qt.Key.Key_Space)
        assert window.selected_indices() == [0]
    finally:
        window.reject()
        window.deleteLater()


def test_planning_error_leaves_preview_available_for_retry(tmp_path, monkeypatch):
    from gaming_buddy.card_pack import CardPackError

    def invalid(*args, **kwargs):
        raise CardPackError("Enter a valid destination game.")

    window = dialog(tmp_path, monkeypatch)
    monkeypatch.setattr("gaming_buddy.card_pack_dialog.plan_card_import", invalid)
    try:
        wait_until(lambda: window.import_button.isEnabled())
        window.accept()
        wait_until(lambda: "valid destination" in window.status.text())
        assert window.isVisible()
        assert window.import_button.isEnabled()
        assert window.card_list.isEnabled()
        assert window.plan is None
    finally:
        window.reject()
        window.deleteLater()


def test_wide_image_preview_fits_after_resizing(qt_application):
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage

    from gaming_buddy.card_pack_dialog import _ImagePreview

    image = QImage(1000, 100, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    data = QBuffer()
    data.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(data, "PNG")
    preview = _ImagePreview()
    try:
        preview.resize(600, 180)
        preview.set_image(bytes(data.data()))
        preview.show()
        QTest.qWait(20)
        preview.resize(300, 180)
        QTest.qWait(20)
        assert not preview.pixmap().isNull()
        assert preview.pixmap().width() <= preview.width() == 300
    finally:
        preview.close()
        preview.deleteLater()


def test_thread_start_failure_is_reported_and_dialog_can_close(tmp_path, monkeypatch):
    def failed_start(_thread):
        raise RuntimeError("No thread resources")

    monkeypatch.setattr(threading.Thread, "start", failed_start)
    window = dialog(tmp_path, monkeypatch)
    try:
        wait_until(lambda: "could not start" in window.status.text())
        assert window.shutdown_ready
        assert not window.import_button.isEnabled()
        window.reject()
        assert not window.isVisible()
    finally:
        window.reject()
        window.deleteLater()
