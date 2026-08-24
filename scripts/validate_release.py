from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")


def _matching_version(text: str, pattern: str, source: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"Could not read the version from {source}.")
    version = match.group(1)
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"Invalid version in {source}: {version}")
    return version


def _matching_quad_version(text: str, pattern: str, source: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"Could not read the version from {source}.")
    parts = match.groups()
    if len(parts) != 4 or parts[-1] != "0":
        raise ValueError(f"Invalid four-part version in {source}: {'.'.join(parts)}")
    return ".".join(parts[:3])


def release_versions() -> dict[str, str]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file:
        project_version = tomllib.load(file)["project"]["version"]

    package_text = (PROJECT_ROOT / "src/gaming_buddy/__init__.py").read_text(
        encoding="utf-8"
    )
    installer_text = (PROJECT_ROOT / "packaging/gaming-buddy.iss").read_text(
        encoding="utf-8"
    )
    executable_text = (PROJECT_ROOT / "packaging/version_info.txt").read_text(
        encoding="utf-8"
    )

    return {
        "pyproject.toml": project_version,
        "gaming_buddy/__init__.py": _matching_version(
            package_text,
            r'^__version__\s*=\s*["\']([^"\']+)["\']',
            "gaming_buddy/__init__.py",
        ),
        "gaming-buddy.iss": _matching_version(
            installer_text,
            r'^#define MyAppVersion\s+"([^"]+)"',
            "gaming-buddy.iss",
        ),
        "gaming-buddy.iss VersionInfoVersion": _matching_quad_version(
            installer_text,
            r"^VersionInfoVersion=(\d+)\.(\d+)\.(\d+)\.(\d+)$",
            "gaming-buddy.iss VersionInfoVersion",
        ),
        "version_info.txt FileVersion": _matching_version(
            executable_text,
            r"StringStruct\('FileVersion',\s*'([^']+)'\)",
            "version_info.txt FileVersion",
        ),
        "version_info.txt ProductVersion": _matching_version(
            executable_text,
            r"StringStruct\('ProductVersion',\s*'([^']+)'\)",
            "version_info.txt ProductVersion",
        ),
        "version_info.txt filevers": _matching_quad_version(
            executable_text,
            r"filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)",
            "version_info.txt filevers",
        ),
        "version_info.txt prodvers": _matching_quad_version(
            executable_text,
            r"prodvers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)",
            "version_info.txt prodvers",
        ),
    }


def validate_release(tag: str | None = None) -> str:
    versions = release_versions()
    distinct_versions = set(versions.values())
    if len(distinct_versions) != 1:
        details = ", ".join(f"{source}={version}" for source, version in versions.items())
        raise ValueError(f"Release versions do not match: {details}")

    version = distinct_versions.pop()
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"Invalid project version: {version}")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"Tag {tag!r} does not match project version v{version}.")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Windows release metadata.")
    parser.add_argument("--tag", help="Require an exact vMAJOR.MINOR.PATCH release tag.")
    arguments = parser.parse_args()

    try:
        version = validate_release(arguments.tag)
    except ValueError as error:
        parser.error(str(error))

    print(f"Release metadata is synchronized at version {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
