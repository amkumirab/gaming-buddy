from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from gaming_buddy.note_drafts import NoteDraftStore


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
