from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gaming_buddy.note_drafts import (
    MAX_DRAFT_FILE_BYTES,
    MAX_DRAFT_TEXT_LENGTH,
    DraftError,
    NoteDraft,
    NoteDraftStore,
)


def test_note_draft_round_trip_preserves_content_and_context(tmp_path: Path) -> None:
    path = tmp_path / "drafts" / "quick-note.json"
    store = NoteDraftStore(path)
    updated_at = datetime(2026, 9, 10, 12, 30, tzinfo=UTC)

    saved = store.save("Code: 0451\nTry the west door.", "  System Shock  ", now=updated_at)

    assert saved == NoteDraft(
        text="Code: 0451\nTry the west door.",
        game="System Shock",
        updated_at="2026-09-10T12:30:00+00:00",
    )
    assert store.load() == saved
    assert not path.with_suffix(".json.tmp").exists()


def test_blank_note_removes_an_existing_draft(tmp_path: Path) -> None:
    path = tmp_path / "quick-note.json"
    store = NoteDraftStore(path)
    store.save("Unsaved clue", "Control")

    assert store.save("  \n ", "Control") is None
    assert store.load() is None
    assert not path.exists()


@pytest.mark.parametrize(
    "content",
    (
        b"not-json",
        b"[]",
        b'{"text":"","game":"Control","updated_at":"2026-09-10T12:30:00+00:00"}',
        b'{"text":"clue","game":"Control","updated_at":"invalid"}',
    ),
)
def test_invalid_draft_files_are_ignored(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "quick-note.json"
    path.write_bytes(content)

    assert NoteDraftStore(path).load() is None


def test_oversized_drafts_are_rejected_without_replacing_the_previous_one(
    tmp_path: Path,
) -> None:
    path = tmp_path / "quick-note.json"
    store = NoteDraftStore(path)
    original = store.save("Keep this clue", "Control")

    with pytest.raises(DraftError, match="too large"):
        store.save("x" * (MAX_DRAFT_TEXT_LENGTH + 1), "Control")

    assert store.load() == original


def test_oversized_draft_file_is_not_loaded(tmp_path: Path) -> None:
    path = tmp_path / "quick-note.json"
    path.write_bytes(b"x" * (MAX_DRAFT_FILE_BYTES + 1))

    assert NoteDraftStore(path).load() is None


def test_clear_removes_draft_and_interrupted_temporary_file(tmp_path: Path) -> None:
    path = tmp_path / "quick-note.json"
    temporary_path = path.with_suffix(".json.tmp")
    path.write_text("saved", encoding="utf-8")
    temporary_path.write_text("partial", encoding="utf-8")

    NoteDraftStore(path).clear()

    assert not path.exists()
    assert not temporary_path.exists()
