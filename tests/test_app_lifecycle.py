from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from gaming_buddy.note_drafts import NoteDraftStore
from gaming_buddy.storage import CardStore


def test_real_app_second_launch_and_normal_shutdown_exit_cleanly(tmp_path):
    script = Path(__file__).parent / "helpers" / "app_lifecycle.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    command = [sys.executable, "-X", "faulthandler", "-u", str(script), str(tmp_path)]
    primary = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    events = queue.Queue()

    def read():
        for line in primary.stdout:
            events.put(line.strip())
        events.put("EXIT")

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        assert events.get(timeout=15) == "READY"
        secondary = subprocess.run(
            command, capture_output=True, text=True, env=environment, timeout=10, check=False
        )
        assert secondary.returncode == 0, secondary.stderr
        assert "READY" not in secondary.stdout
        assert events.get(timeout=10) == "ACTIVATED"
        assert primary.wait(timeout=15) == 0, primary.stderr.read()
    finally:
        if primary.poll() is None:
            primary.kill()
        primary.wait(timeout=5)
        reader.join(timeout=5)
        primary.stdout.close()
        primary.stderr.close()


@pytest.mark.parametrize("mode", ["check", "download", "recognition"])
def test_real_app_busy_exit_drains_tasks_and_preserves_draft(tmp_path, mode):
    script = Path(__file__).parent / "helpers" / "app_lifecycle.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-u", str(script), str(tmp_path), mode],
        capture_output=True, text=True, env=environment, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "WAITING" in result.stdout
    assert "RESPONSIVE" in result.stdout
    assert "PREMATURE" not in result.stdout
    assert NoteDraftStore(tmp_path / "data/drafts/quick-note.json").load().text == "Busy exit clue"
    assert list((tmp_path / "data/captures").glob("*.png")) == []


def test_real_app_quick_panel_exit_preserves_the_shared_draft(tmp_path):
    script = Path(__file__).parent / "helpers" / "app_lifecycle.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-u", str(script), str(tmp_path), "quick_panel"],
        capture_output=True, text=True, env=environment, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "QUICK_VISIBLE" in result.stdout
    assert NoteDraftStore(tmp_path / "data/drafts/quick-note.json").load().text == "Quick panel exit clue"


def test_real_app_walkthrough_resumes_saved_note_and_exits_cleanly(tmp_path):
    script = Path(__file__).parent / "helpers" / "app_lifecycle.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    native = QSettings("GamingBuddy", "GamingBuddy")
    original_keys = native.allKeys()
    original_values = [native.value(key) for key in original_keys]
    for mode in ("walkthrough", "walkthrough_resume"):
        result = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-u", str(script), str(tmp_path), mode],
            capture_output=True, text=True, env=environment, timeout=20, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "WALKTHROUGH_OK" in result.stdout
    saved = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert saved.value("onboarding/walkthrough/step", type=int) == 2
    native.sync()
    assert native.allKeys() == original_keys
    assert [native.value(key) for key in original_keys] == original_values
    with CardStore(tmp_path / "data/gaming-buddy.sqlite3") as store:
        cards = store.list()
        assert len(cards) == 1
        assert cards[0].content == "My first clue\n\nKeep this note"
        assert cards[0].pinned


@pytest.mark.parametrize("busy", [False, True])
def test_real_capture_text_review_and_busy_shutdown_keep_original_image(tmp_path, busy):
    script = Path(__file__).parent / "helpers" / "app_lifecycle.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    mode = "capture_text_busy" if busy else "capture_text"
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-u", str(script), str(tmp_path), mode],
        capture_output=True, text=True, env=environment, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CAPTURE_TEXT_READY" in result.stdout
    assert ("WAITING" in result.stdout) if busy else ("CAPTURE_TEXT_SAVED" in result.stdout)
    if busy:
        assert "RESPONSIVE" in result.stdout
        assert NoteDraftStore(tmp_path / "data/drafts/quick-note.json").load().text == "Capture text draft"
    with CardStore(tmp_path / "data/gaming-buddy.sqlite3") as store:
        cards = store.list()
        assert len(cards) == 1 and Path(cards[0].image_path).is_file()
        assert cards[0].content == ("" if busy else "Reviewed code\n0451")
        assert not cards[0].pinned
