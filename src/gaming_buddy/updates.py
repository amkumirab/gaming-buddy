from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

from gaming_buddy import __version__

LATEST_RELEASE_URL = "https://api.github.com/repos/amkumirab/gaming-buddy/releases/latest"
RELEASE_DOWNLOAD_PREFIX = (
    "https://github.com/amkumirab/gaming-buddy/releases/download/"
)
RELEASE_PAGE_PREFIX = "https://github.com/amkumirab/gaming-buddy/releases/"
USER_AGENT = f"Gaming-Buddy/{__version__}"
CHECK_INTERVAL = timedelta(hours=24)
NETWORK_TIMEOUT_SECONDS = 20
MAX_RELEASE_BYTES = 2 * 1024 * 1024
MAX_CHECKSUM_BYTES = 16 * 1024
MAX_INSTALLER_BYTES = 512 * 1024 * 1024
ALLOWED_UPDATE_HOSTS = {
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)
CHECKSUM_PATTERN = re.compile(r"([0-9a-fA-F]{64})\s+\*?(.+)")


class UpdateError(RuntimeError):
    pass


class UpdateCancelled(UpdateError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    tag_name: str
    title: str
    notes: str
    page_url: str
    published_at: str
    installer: ReleaseAsset
    checksum: ReleaseAsset


class NetworkResponse(Protocol):
    headers: Any

    def __enter__(self) -> Self: ...

    def __exit__(self, *_args: object) -> None: ...

    def read(self, size: int = -1) -> bytes: ...

    def geturl(self) -> str: ...


NetworkOpener = Callable[..., NetworkResponse]
ProgressCallback = Callable[[int, int], None]


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported version: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    return parse_version(candidate) > parse_version(current)


def should_check_automatically(
    last_attempt: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not last_attempt:
        return True
    try:
        checked_at = datetime.fromisoformat(last_attempt)
    except ValueError:
        return True
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    current_time = now or datetime.now(UTC)
    return current_time - checked_at.astimezone(UTC) >= CHECK_INTERVAL


def parse_release_payload(payload: bytes | str | dict[str, Any]) -> ReleaseInfo:
    if isinstance(payload, bytes):
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateError("The update service returned an invalid response.") from exc
    elif isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise UpdateError("The update service returned an invalid response.") from exc
    else:
        data = payload
    if not isinstance(data, dict):
        raise UpdateError("The update service returned an invalid response.")

    tag_name = str(data.get("tag_name", "")).strip()
    try:
        version_tuple = parse_version(tag_name)
    except ValueError as exc:
        raise UpdateError("The latest release has an unsupported version number.") from exc
    version = ".".join(str(part) for part in version_tuple)
    page_url = str(data.get("html_url", "")).strip()
    if not page_url.startswith(RELEASE_PAGE_PREFIX):
        raise UpdateError("The latest release contains an invalid page link.")

    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("The latest release does not include Windows downloads.")
    installer_name = f"Gaming-Buddy-Setup-{version}-x64.exe"
    checksum_name = f"{installer_name}.sha256"
    assets_by_name = {
        str(asset.get("name", "")): asset
        for asset in assets
        if isinstance(asset, dict)
    }
    installer = _release_asset(assets_by_name.get(installer_name), installer_name)
    checksum = _release_asset(assets_by_name.get(checksum_name), checksum_name)
    if installer.size <= 0 or installer.size > MAX_INSTALLER_BYTES:
        raise UpdateError("The Windows installer has an invalid size.")
    if checksum.size <= 0 or checksum.size > MAX_CHECKSUM_BYTES:
        raise UpdateError("The installer checksum has an invalid size.")

    return ReleaseInfo(
        version=version,
        tag_name=tag_name,
        title=str(data.get("name", "")).strip() or f"Gaming Buddy {tag_name}",
        notes=str(data.get("body", "")).strip()[:20_000],
        page_url=page_url,
        published_at=str(data.get("published_at", "")).strip(),
        installer=installer,
        checksum=checksum,
    )


def fetch_latest_release(*, opener: NetworkOpener = urlopen) -> ReleaseInfo:
    payload = _read_url(LATEST_RELEASE_URL, MAX_RELEASE_BYTES, opener=opener)
    return parse_release_payload(payload)


def parse_checksum(contents: bytes | str, expected_filename: str) -> str:
    if isinstance(contents, bytes):
        try:
            text = contents.decode("ascii")
        except UnicodeDecodeError as exc:
            raise UpdateError("The installer checksum is invalid.") from exc
    else:
        text = contents
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise UpdateError("The installer checksum is invalid.")
    match = CHECKSUM_PATTERN.fullmatch(lines[0])
    if match is None or match.group(2) != expected_filename:
        raise UpdateError("The installer checksum does not match this download.")
    return match.group(1).lower()


def download_release(
    release: ReleaseInfo,
    destination_dir: Path,
    *,
    progress: ProgressCallback | None = None,
    cancelled: threading.Event | None = None,
    opener: NetworkOpener = urlopen,
) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    checksum_bytes = _read_url(
        release.checksum.download_url,
        MAX_CHECKSUM_BYTES,
        opener=opener,
    )
    expected_digest = parse_checksum(checksum_bytes, release.installer.name)
    destination = destination_dir / release.installer.name
    partial = destination.with_suffix(f"{destination.suffix}.part")
    partial.unlink(missing_ok=True)
    try:
        actual_digest = _download_file(
            release.installer.download_url,
            partial,
            expected_size=release.installer.size,
            progress=progress,
            cancelled=cancelled,
            opener=opener,
        )
        if actual_digest != expected_digest:
            raise UpdateError("The downloaded installer failed its integrity check.")
        os.replace(partial, destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return destination


class UpdateController(QObject):
    update_available = Signal(object)
    up_to_date = Signal(object)
    check_failed = Signal(str)
    download_progress = Signal(int, int)
    download_ready = Signal(str, object)
    download_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._checking = False
        self._downloading = False
        self._cancel_download = threading.Event()

    @property
    def checking(self) -> bool:
        return self._checking

    @property
    def downloading(self) -> bool:
        return self._downloading

    def check_for_updates(self) -> bool:
        if self._checking or self._downloading:
            return False
        self._checking = True
        threading.Thread(target=self._check_worker, daemon=True).start()
        return True

    def download_update(self, release: ReleaseInfo, destination_dir: Path) -> bool:
        if self._checking or self._downloading:
            return False
        self._downloading = True
        self._cancel_download.clear()
        threading.Thread(
            target=self._download_worker,
            args=(release, destination_dir),
            daemon=True,
        ).start()
        return True

    def cancel_download(self) -> None:
        if self._downloading:
            self._cancel_download.set()

    def _check_worker(self) -> None:
        try:
            release = fetch_latest_release()
            if is_newer_version(release.version):
                self.update_available.emit(release)
            else:
                self.up_to_date.emit(release)
        except (UpdateError, HTTPError, URLError, OSError, TimeoutError) as exc:
            self.check_failed.emit(_friendly_network_error(exc))
        finally:
            self._checking = False

    def _download_worker(self, release: ReleaseInfo, destination_dir: Path) -> None:
        try:
            installer = download_release(
                release,
                destination_dir,
                progress=lambda received, total: self.download_progress.emit(received, total),
                cancelled=self._cancel_download,
            )
            self.download_ready.emit(str(installer), release)
        except UpdateCancelled:
            self.download_failed.emit("Update download cancelled.")
        except (UpdateError, HTTPError, URLError, OSError, TimeoutError) as exc:
            self.download_failed.emit(_friendly_network_error(exc))
        finally:
            self._downloading = False


def _release_asset(value: Any, expected_name: str) -> ReleaseAsset:
    if not isinstance(value, dict):
        raise UpdateError(f"The latest release is missing {expected_name}.")
    url = str(value.get("browser_download_url", "")).strip()
    if not url.startswith(RELEASE_DOWNLOAD_PREFIX):
        raise UpdateError("The latest release contains an invalid download link.")
    try:
        size = int(value.get("size", -1))
    except (TypeError, ValueError) as exc:
        raise UpdateError("The latest release contains an invalid download size.") from exc
    return ReleaseAsset(expected_name, url, size)


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def _read_url(url: str, limit: int, *, opener: NetworkOpener) -> bytes:
    with opener(_request(url), timeout=NETWORK_TIMEOUT_SECONDS) as response:
        _validate_response_url(response)
        declared_size = _content_length(response)
        if declared_size is not None and declared_size > limit:
            raise UpdateError("The update service response is too large.")
        result = response.read(limit + 1)
    if len(result) > limit:
        raise UpdateError("The update service response is too large.")
    return result


def _download_file(
    url: str,
    destination: Path,
    *,
    expected_size: int,
    progress: ProgressCallback | None,
    cancelled: threading.Event | None,
    opener: NetworkOpener,
) -> str:
    digest = hashlib.sha256()
    received = 0
    with opener(_request(url), timeout=NETWORK_TIMEOUT_SECONDS) as response:
        _validate_response_url(response)
        declared_size = _content_length(response)
        if declared_size is not None and declared_size > MAX_INSTALLER_BYTES:
            raise UpdateError("The Windows installer is too large to download safely.")
        total = declared_size or expected_size
        with destination.open("wb") as output:
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise UpdateCancelled("Update download cancelled.")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > MAX_INSTALLER_BYTES:
                    raise UpdateError("The Windows installer is too large to download safely.")
                output.write(chunk)
                digest.update(chunk)
                if progress is not None:
                    progress(received, total)
    if received != expected_size:
        raise UpdateError("The downloaded installer size does not match the release.")
    return digest.hexdigest()


def _content_length(response: NetworkResponse) -> int | None:
    value = response.headers.get("Content-Length")
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _validate_response_url(response: NetworkResponse) -> None:
    final_url = urlparse(response.geturl())
    if final_url.scheme != "https" or final_url.hostname not in ALLOWED_UPDATE_HOSTS:
        raise UpdateError("The update service redirected to an untrusted location.")


def _friendly_network_error(error: Exception) -> str:
    if isinstance(error, UpdateError):
        return str(error)
    if isinstance(error, HTTPError) and error.code == 404:
        return "No published Gaming Buddy release is available yet."
    if isinstance(error, HTTPError):
        return f"The update service returned HTTP {error.code}."
    if isinstance(error, (URLError, TimeoutError)):
        return "Could not connect to the update service. Check your internet connection."
    return f"The update could not be completed: {error}"
