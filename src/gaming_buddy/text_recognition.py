from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_POWERSHELL_SCRIPT = r"""
$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapTransform, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]

function Await($Operation, $ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.GetGenericTypeDefinition().FullName -eq
                'Windows.Foundation.IAsyncOperation`1'
        } | Select-Object -First 1
    if ($null -eq $method) { throw 'Windows async support is unavailable.' }
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

try {
    if ($env:GB_TEXT_MODE -eq 'languages') {
        $languages = @(
            [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages |
                ForEach-Object {
                    [pscustomobject]@{
                        tag = $_.LanguageTag
                        display_name = $_.DisplayName
                    }
                }
        )
        [pscustomobject]@{
            languages = $languages
            max_image_dimension = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
        } | ConvertTo-Json -Compress -Depth 3
        exit 0
    }

    $stream = $null
    $bitmap = $null
    try {
        $file = Await (
            [Windows.Storage.StorageFile]::GetFileFromPathAsync($env:GB_TEXT_IMAGE)
        ) ([Windows.Storage.StorageFile])
        $stream = Await (
            $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
        ) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await (
            [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
        ) ([Windows.Graphics.Imaging.BitmapDecoder])

        $maximum = [double][Windows.Media.Ocr.OcrEngine]::MaxImageDimension
        if ($decoder.PixelWidth -gt $maximum -or $decoder.PixelHeight -gt $maximum) {
            $scale = [Math]::Min($maximum / $decoder.PixelWidth, $maximum / $decoder.PixelHeight)
            $transform = [Windows.Graphics.Imaging.BitmapTransform]::new()
            $transform.ScaledWidth = [uint32][Math]::Max(1, [Math]::Round($decoder.PixelWidth * $scale))
            $transform.ScaledHeight = [uint32][Math]::Max(1, [Math]::Round($decoder.PixelHeight * $scale))
            $bitmap = Await (
                $decoder.GetSoftwareBitmapAsync(
                    [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
                    [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied,
                    $transform,
                    [Windows.Graphics.Imaging.ExifOrientationMode]::RespectExifOrientation,
                    [Windows.Graphics.Imaging.ColorManagementMode]::ColorManageToSRgb
                )
            ) ([Windows.Graphics.Imaging.SoftwareBitmap])
        } else {
            $bitmap = Await (
                $decoder.GetSoftwareBitmapAsync()
            ) ([Windows.Graphics.Imaging.SoftwareBitmap])
        }

        if ($env:GB_TEXT_LANGUAGE) {
            $language = [Windows.Globalization.Language]::new($env:GB_TEXT_LANGUAGE)
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
        } else {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
        }
        if ($null -eq $engine) { throw 'The selected recognition language is unavailable.' }

        $result = Await (
            $engine.RecognizeAsync($bitmap)
        ) ([Windows.Media.Ocr.OcrResult])
        [pscustomobject]@{
            text = $result.Text
            language = $engine.RecognizerLanguage.LanguageTag
        } | ConvertTo-Json -Compress
    } finally {
        if ($null -ne $bitmap) { $bitmap.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
"""


class TextRecognitionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RecognitionLanguage:
    tag: str
    display_name: str


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    text: str
    language: str


def available_languages(*, timeout: float = 8.0) -> list[RecognitionLanguage]:
    payload = _run_windows_recognizer("languages", timeout=timeout)
    raw_languages = payload.get("languages", [])
    if not isinstance(raw_languages, list):
        raise TextRecognitionError("Windows returned an invalid language list.")
    languages: list[RecognitionLanguage] = []
    for item in raw_languages:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag", "")).strip()
        display_name = str(item.get("display_name", "")).strip()
        if tag:
            languages.append(RecognitionLanguage(tag, display_name or tag))
    return languages


def recognize_text(
    image_path: Path,
    language: str = "",
    *,
    timeout: float = 45.0,
) -> RecognitionResult:
    image_path = image_path.resolve()
    if not image_path.is_file():
        raise TextRecognitionError("The screenshot file could not be found.")
    payload = _run_windows_recognizer(
        "recognize",
        image_path=image_path,
        language=language,
        timeout=timeout,
    )
    return RecognitionResult(
        text=str(payload.get("text", "")).strip(),
        language=str(payload.get("language", "")).strip(),
    )


def _run_windows_recognizer(
    mode: str,
    *,
    image_path: Path | None = None,
    language: str = "",
    timeout: float,
) -> dict[str, Any]:
    if sys.platform != "win32":
        raise TextRecognitionError("Local text recognition requires Windows 10 or newer.")
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        raise TextRecognitionError("Windows text recognition could not be started.")

    environment = os.environ.copy()
    environment["GB_TEXT_MODE"] = mode
    environment["GB_TEXT_IMAGE"] = str(image_path or "")
    environment["GB_TEXT_LANGUAGE"] = language.strip()
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _POWERSHELL_SCRIPT,
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
            env=environment,
            creationflags=creation_flags,
        )
    except subprocess.TimeoutExpired as exc:
        raise TextRecognitionError("Text recognition took too long to finish.") from exc
    except OSError as exc:
        raise TextRecognitionError("Windows text recognition could not be started.") from exc

    stdout = completed.stdout.decode("utf-8-sig", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8-sig", errors="replace").strip()
    if completed.returncode != 0:
        message = stderr.splitlines()[-1] if stderr else "Windows could not read this image."
        raise TextRecognitionError(message)
    try:
        payload = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TextRecognitionError("Windows returned an invalid text recognition result.") from exc
    if not isinstance(payload, dict):
        raise TextRecognitionError("Windows returned an invalid text recognition result.")
    return payload
