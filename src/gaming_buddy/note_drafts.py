from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MAX_DRAFT_TEXT_LENGTH = 250_000
MAX_DRAFT_FILE_BYTES = 1024 * 1024


class DraftError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NoteDraft:
    text: str
    game: str
    updated_at: str


class NoteDraftStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> NoteDraft | None:
        try:
            if not self.path.is_file() or self.path.stat().st_size > MAX_DRAFT_FILE_BYTES:
                return None
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        text = payload.get("text")
        game = payload.get("game")
        updated_at = payload.get("updated_at")
        if not all(isinstance(value, str) for value in (text, game, updated_at)):
            return None
        if not text.strip() or len(text) > MAX_DRAFT_TEXT_LENGTH:
            return None
        try:
            timestamp = datetime.fromisoformat(updated_at)
        except ValueError:
            return None
        if timestamp.tzinfo is None:
            return None
        return NoteDraft(text=text, game=game, updated_at=updated_at)

    def save(
        self,
        text: str,
        game: str,
        *,
        now: datetime | None = None,
    ) -> NoteDraft | None:
        if not text.strip():
            self.clear()
            return None
        if len(text) > MAX_DRAFT_TEXT_LENGTH:
            raise DraftError("The note is too large to save as a draft.")
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        draft = NoteDraft(text=text, game=game.strip(), updated_at=timestamp.isoformat())
        encoded = json.dumps(
            {
                "text": draft.text,
                "game": draft.game,
                "updated_at": draft.updated_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_DRAFT_FILE_BYTES:
            raise DraftError("The note is too large to save as a draft.")

        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self.path)
        except OSError as error:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise DraftError(f"Could not save the note draft: {error}") from error
        return draft

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
            self.path.with_suffix(f"{self.path.suffix}.tmp").unlink(missing_ok=True)
        except OSError as error:
            raise DraftError(f"Could not remove the note draft: {error}") from error
