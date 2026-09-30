from __future__ import annotations

import hashlib
import io
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Self
from urllib.error import HTTPError
from urllib.request import Request

import pytest

import gaming_buddy.updates as updates_module
from gaming_buddy import __version__
from gaming_buddy.updates import (
    CHECK_INTERVAL,
    UpdateCancelled,
    UpdateController,
    UpdateError,
    download_release,
    is_newer_version,
    parse_checksum,
    parse_release_payload,
    parse_version,
    should_check_automatically,
)


class FakeResponse:
    def __init__(self, content: bytes, url: str) -> None:
        self.stream = io.BytesIO(content)
        self.headers = {"Content-Length": str(len(content))}
        self.url = url

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)

    def geturl(self) -> str:
        return self.url


def _release_payload(installer_content: bytes = b"windows-installer") -> dict[str, object]:
    version = "1.2.3"
    installer_name = f"Gaming-Buddy-Setup-{version}-x64.exe"
    checksum = f"{hashlib.sha256(installer_content).hexdigest()}  {installer_name}\n"
    return {
        "tag_name": f"v{version}",
        "name": "Gaming Buddy 1.2.3",
        "body": "Faster startup and a more reliable overlay.",
        "html_url": "https://github.com/amkumirab/gaming-buddy/releases/tag/v1.2.3",
        "published_at": "2026-09-09T08:00:00Z",
        "assets": [
            {
                "name": installer_name,
                "browser_download_url": (
                    "https://github.com/amkumirab/gaming-buddy/releases/download/"
                    f"v{version}/{installer_name}"
                ),
                "size": len(installer_content),
            },
            {
                "name": f"{installer_name}.sha256",
                "browser_download_url": (
                    "https://github.com/amkumirab/gaming-buddy/releases/download/"
                    f"v{version}/{installer_name}.sha256"
                ),
                "size": len(checksum.encode("ascii")),
            },
        ],
    }


def test_versions_are_compared_numerically() -> None:
    assert parse_version("v1.12.3") == (1, 12, 3)
    assert is_newer_version("0.10.0", "0.9.9") is True
    assert is_newer_version("1.0.0", "1.0.0") is False
    with pytest.raises(ValueError, match="Unsupported version"):
        parse_version("1.2")


def test_update_check_reports_no_published_release(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable() -> None:
        raise HTTPError(updates_module.LATEST_RELEASE_URL, 404, "Not Found", {}, None)

    monkeypatch.setattr(updates_module, "fetch_latest_release", unavailable)
    controller = UpdateController()
    failures: list[str] = []
    available: list[object] = []
    current: list[object] = []
    controller.check_failed.connect(failures.append)
    controller.update_available.connect(available.append)
    controller.up_to_date.connect(current.append)
    controller._checking = True

    controller._check_worker()

    assert failures == ["No published Gaming Buddy release is available yet."]
    assert available == current == []
    assert not controller.checking


@pytest.mark.parametrize("newer", [False, True])
def test_update_check_distinguishes_current_and_newer_releases(
    monkeypatch: pytest.MonkeyPatch,
    newer: bool,
) -> None:
    major, minor, patch = parse_version(__version__)
    version = f"{major}.{minor}.{patch + 1}" if newer else __version__
    payload = _release_payload()
    payload["tag_name"] = f"v{version}"
    payload["html_url"] = f"{updates_module.RELEASE_PAGE_PREFIX}tag/v{version}"
    assets = payload["assets"]
    assert isinstance(assets, list)
    for asset in assets:
        asset["name"] = asset["name"].replace("1.2.3", version)
        asset["browser_download_url"] = asset["browser_download_url"].replace("1.2.3", version)
    release = parse_release_payload(payload)
    monkeypatch.setattr(updates_module, "fetch_latest_release", lambda: release)
    controller = UpdateController()
    available: list[object] = []
    current: list[object] = []
    failures: list[str] = []
    controller.update_available.connect(available.append)
    controller.up_to_date.connect(current.append)
    controller.check_failed.connect(failures.append)
    controller._checking = True

    controller._check_worker()

    assert available == ([release] if newer else [])
    assert current == ([] if newer else [release])
    assert failures == []
    assert not controller.checking


def test_release_payload_selects_matching_verified_assets() -> None:
    release = parse_release_payload(_release_payload())

    assert release.version == "1.2.3"
    assert release.title == "Gaming Buddy 1.2.3"
    assert release.installer.name == "Gaming-Buddy-Setup-1.2.3-x64.exe"
    assert release.checksum.name.endswith(".sha256")
    assert release.notes.startswith("Faster startup")


def test_release_payload_rejects_missing_or_foreign_downloads() -> None:
    missing = _release_payload()
    missing["assets"] = []
    with pytest.raises(UpdateError, match="missing"):
        parse_release_payload(missing)

    foreign = _release_payload()
    assets = foreign["assets"]
    assert isinstance(assets, list) and isinstance(assets[0], dict)
    assets[0]["browser_download_url"] = "https://example.com/setup.exe"
    with pytest.raises(UpdateError, match="invalid download link"):
        parse_release_payload(foreign)


def test_automatic_checks_are_limited_to_once_per_day() -> None:
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)

    assert should_check_automatically(None, now=now) is True
    assert should_check_automatically("invalid", now=now) is True
    assert should_check_automatically((now - CHECK_INTERVAL / 2).isoformat(), now=now) is False
    assert should_check_automatically((now - CHECK_INTERVAL - timedelta(seconds=1)).isoformat(), now=now)


def test_checksum_requires_the_exact_installer_name() -> None:
    digest = "a" * 64
    assert parse_checksum(f"{digest}  Gaming-Buddy-Setup-1.2.3-x64.exe\n", "Gaming-Buddy-Setup-1.2.3-x64.exe") == digest
    with pytest.raises(UpdateError, match="does not match"):
        parse_checksum(f"{digest}  another.exe", "Gaming-Buddy-Setup-1.2.3-x64.exe")


def test_release_download_is_verified_before_it_replaces_the_installer(tmp_path: Path) -> None:
    installer_content = b"verified-windows-installer"
    release = parse_release_payload(_release_payload(installer_content))
    checksum_content = (
        f"{hashlib.sha256(installer_content).hexdigest()}  {release.installer.name}\n"
    ).encode("ascii")
    responses = {
        release.checksum.download_url: checksum_content,
        release.installer.download_url: installer_content,
    }
    progress: list[tuple[int, int]] = []

    def opener(request: Request, **_kwargs: object) -> FakeResponse:
        return FakeResponse(responses[request.full_url], request.full_url)

    destination = download_release(
        release,
        tmp_path,
        opener=opener,
        progress=lambda received, total: progress.append((received, total)),
    )

    assert destination.read_bytes() == installer_content
    assert progress[-1] == (len(installer_content), len(installer_content))
    assert not destination.with_suffix(".exe.part").exists()


def test_cancelled_or_modified_downloads_leave_no_partial_installer(tmp_path: Path) -> None:
    installer_content = b"expected-installer"
    release = parse_release_payload(_release_payload(installer_content))
    checksum_content = (
        f"{hashlib.sha256(installer_content).hexdigest()}  {release.installer.name}\n"
    ).encode("ascii")

    def modified_opener(request: Request, **_kwargs: object) -> FakeResponse:
        if request.full_url == release.checksum.download_url:
            return FakeResponse(checksum_content, request.full_url)
        return FakeResponse(b"modified-installer", request.full_url)

    with pytest.raises(UpdateError):
        download_release(release, tmp_path, opener=modified_opener)
    assert list(tmp_path.iterdir()) == []

    cancelled = threading.Event()
    cancelled.set()

    def valid_opener(request: Request, **_kwargs: object) -> FakeResponse:
        content = (
            checksum_content
            if request.full_url == release.checksum.download_url
            else installer_content
        )
        return FakeResponse(content, request.full_url)

    with pytest.raises(UpdateCancelled):
        download_release(release, tmp_path, opener=valid_opener, cancelled=cancelled)
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_an_untrusted_redirect(tmp_path: Path) -> None:
    installer_content = b"expected-installer"
    release = parse_release_payload(_release_payload(installer_content))

    def opener(_request: Request, **_kwargs: object) -> FakeResponse:
        return FakeResponse(b"response", "https://example.com/redirected")

    with pytest.raises(UpdateError, match="untrusted location"):
        download_release(release, tmp_path, opener=opener)
    assert list(tmp_path.iterdir()) == []
