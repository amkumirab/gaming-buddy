from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from gaming_buddy import text_recognition
from gaming_buddy.text_recognition import (
    RecognitionLanguage,
    RecognitionResult,
    TextRecognitionError,
)


def test_available_languages_ignores_invalid_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        text_recognition,
        "_run_windows_recognizer",
        lambda _mode, **_kwargs: {
            "languages": [
                {"tag": "en-US", "display_name": "English (United States)"},
                {"tag": "it-IT", "display_name": ""},
                {"display_name": "Missing tag"},
                "invalid",
            ]
        },
    )

    assert text_recognition.available_languages() == [
        RecognitionLanguage("en-US", "English (United States)"),
        RecognitionLanguage("it-IT", "it-IT"),
    ]


def test_recognize_text_returns_trimmed_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "safe code.png"
    image.write_bytes(b"image")
    received: dict[str, object] = {}

    def fake_runner(mode: str, **kwargs: object) -> dict[str, str]:
        received["mode"] = mode
        received.update(kwargs)
        return {"text": "  SAFE CODE 0451\r\n", "language": "en-US"}

    monkeypatch.setattr(text_recognition, "_run_windows_recognizer", fake_runner)

    assert text_recognition.recognize_text(image, "en-US") == RecognitionResult(
        "SAFE CODE 0451",
        "en-US",
    )
    assert received["mode"] == "recognize"
    assert received["image_path"] == image.resolve()
    assert received["language"] == "en-US"


def test_recognize_text_rejects_missing_image(tmp_path: Path) -> None:
    with pytest.raises(TextRecognitionError, match="could not be found"):
        text_recognition.recognize_text(tmp_path / "missing.png")


def test_windows_runner_passes_user_values_through_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "capture & name.png"
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=b'{"text":"Lobby map","language":"en-US"}',
            stderr=b"",
        )

    monkeypatch.setattr(text_recognition.sys, "platform", "win32")
    monkeypatch.setattr(text_recognition.shutil, "which", lambda _name: "powershell.exe")
    monkeypatch.setattr(text_recognition.subprocess, "run", fake_run)

    payload = text_recognition._run_windows_recognizer(
        "recognize",
        image_path=image,
        language="en-US",
        timeout=5,
    )

    assert payload == {"text": "Lobby map", "language": "en-US"}
    command = captured["command"]
    assert isinstance(command, list)
    assert str(image) not in command
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["GB_TEXT_IMAGE"] == str(image)
    assert environment["GB_TEXT_LANGUAGE"] == "en-US"
    assert captured["check"] is False


def test_windows_runner_reports_process_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_recognition.sys, "platform", "win32")
    monkeypatch.setattr(text_recognition.shutil, "which", lambda _name: "powershell.exe")
    monkeypatch.setattr(
        text_recognition.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout=b"",
            stderr=b"Details\r\nSelected language is unavailable.",
        ),
    )

    with pytest.raises(TextRecognitionError, match="Selected language is unavailable"):
        text_recognition._run_windows_recognizer("languages", timeout=5)


def test_windows_runner_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_recognition.sys, "platform", "win32")
    monkeypatch.setattr(text_recognition.shutil, "which", lambda _name: "powershell.exe")

    def time_out(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("powershell.exe", 1)

    monkeypatch.setattr(text_recognition.subprocess, "run", time_out)

    with pytest.raises(TextRecognitionError, match="too long"):
        text_recognition._run_windows_recognizer("languages", timeout=1)


def test_windows_script_scales_oversized_images_before_recognition() -> None:
    script = text_recognition._POWERSHELL_SCRIPT

    assert "MaxImageDimension" in script
    assert "ScaledWidth" in script
    assert "ScaledHeight" in script
