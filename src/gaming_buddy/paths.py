from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "GamingBuddy"


def data_dir() -> Path:
    """Return the per-user data directory without creating it."""
    root = os.getenv("LOCALAPPDATA")
    if root:
        return Path(root) / APP_NAME
    return Path.home() / ".gaming-buddy"


def ensure_data_dirs(root: Path | None = None) -> tuple[Path, Path]:
    base = root or data_dir()
    captures = base / "captures"
    captures.mkdir(parents=True, exist_ok=True)
    return base, captures
