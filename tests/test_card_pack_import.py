from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

import gaming_buddy.card_pack_import as import_module
from gaming_buddy.card_export import create_card_export
from gaming_buddy.card_pack import CardPack, CardPackError, load_card_pack
from gaming_buddy.card_pack_import import commit_card_import, plan_card_import
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.fixture
def pack(tmp_path):
    image = QImage(20, 10, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    source = tmp_path / "source.png"
    assert image.save(str(source))
    path = tmp_path / "export.zip"
    create_card_export(path, [
        Card(None, CardKind.NOTE, "Game", "Clue", content="First\n\nLast\n", tags=("map",)),
        Card(None, CardKind.IMAGE, "Game", "Map", image_path=str(source)),
        Card(None, CardKind.IMAGE, "Game", "Missing", image_path=str(tmp_path / "missing.png")),
    ])
    return load_card_pack(path)


def test_selected_import_is_idempotent_and_never_changes_existing_cards(tmp_path, pack):
    captures = tmp_path / "captures"
    with CardStore(tmp_path / "cards.sqlite3") as store:
        original = store.add(Card(None, CardKind.NOTE, "Other", "Keep", content="Unsaved route"))
        plan = plan_card_import(pack, [0, 1], store.list(), captures, game="Destination")
        assert not captures.exists()
        result = commit_card_import(plan, store, captures)
        assert result.imported == 2 and result.duplicates == 0
        assert store.get(original.id) == original
        imported = store.list("Destination")
        assert len(imported) == 2 and all(not card.pinned for card in imported)
        assert next(card for card in imported if card.kind is CardKind.NOTE).content == "First\n\nLast\n"
        image = next(card for card in imported if card.kind is CardKind.IMAGE)
        assert Path(image.image_path).read_bytes() == pack.cards[1].image.data
        before = set(captures.iterdir())
        second = plan_card_import(pack, [0, 1], store.list(), captures, game="Destination")
        again = commit_card_import(second, store, captures)
        assert again.imported == 0 and again.duplicates == 2
        assert set(captures.iterdir()) == before


def test_batch_insertion_failure_rolls_back_cards_and_tags(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        original = store.add(Card(None, CardKind.NOTE, "Game", "Keep"))
        store._connection.execute("""
            CREATE TRIGGER reject_import BEFORE INSERT ON cards
            WHEN NEW.title = 'Fail' BEGIN SELECT RAISE(ABORT, 'Test failure'); END
        """)
        with pytest.raises(sqlite3.Error):
            store.add_many([
                Card(None, CardKind.NOTE, "Game", "First", tags=("new-tag",)),
                Card(None, CardKind.NOTE, "Game", "Fail"),
            ])
        assert store.list() == [original]
        assert store._connection.execute("SELECT COUNT(*) FROM card_tags").fetchone()[0] == 0


@pytest.mark.parametrize("content", ["First\nLast\n", "First\n\nLast", "first\n\nLast\n",
                                     "First\n\n  Last\n"])
def test_changed_note_content_is_not_considered_a_duplicate(tmp_path, pack, content):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        store.add(Card(None, CardKind.NOTE, "Game", "Clue", content=content, tags=("map",)))
        plan = plan_card_import(pack, [0], store.list(), tmp_path / "captures")
        assert len(plan.cards) == 1 and plan.duplicates == 0


def test_identical_cards_within_one_pack_are_collapsed(tmp_path, pack):
    repeated = CardPack((pack.cards[0], pack.cards[0]))
    plan = plan_card_import(repeated, [0, 1], [], tmp_path / "captures")
    assert len(plan.cards) == 1 and plan.duplicates == 1


@pytest.mark.parametrize("indices", [[], [-1], [999], [True], [0, 0]])
def test_invalid_selection_has_no_side_effects(tmp_path, pack, indices):
    with pytest.raises(CardPackError):
        plan_card_import(pack, indices, [], tmp_path / "captures")
    assert not (tmp_path / "captures").exists()


def test_missing_image_cards_are_reported_without_writing(tmp_path, pack):
    captures = tmp_path / "captures"
    with CardStore(tmp_path / "cards.sqlite3") as store:
        plan = plan_card_import(pack, [2], [], captures)
        result = commit_card_import(plan, store, captures)
        assert result.imported == 0 and result.missing_images == 1
        assert store.list() == [] and not captures.exists()


def test_database_failure_removes_only_new_image_copies(tmp_path, pack):
    captures = tmp_path / "captures"
    captures.mkdir()
    keep = captures / "keep.png"
    keep.write_bytes(b"existing data")
    with CardStore(tmp_path / "cards.sqlite3") as store:
        original = store.add(Card(None, CardKind.NOTE, "Game", "Keep"))
        store._connection.execute("""
            CREATE TRIGGER reject_pack BEFORE INSERT ON cards
            WHEN NEW.title = 'Map' BEGIN SELECT RAISE(ABORT, 'Test failure'); END
        """)
        plan = plan_card_import(pack, [0, 1], store.list(), captures)
        with pytest.raises(CardPackError):
            commit_card_import(plan, store, captures)
        assert store.list() == [original]
        assert list(captures.iterdir()) == [keep]
        assert keep.read_bytes() == b"existing data"


@pytest.mark.parametrize("failure", ["write", "close"])
def test_partial_image_write_or_close_failure_is_cleaned_up(tmp_path, pack, monkeypatch, failure):
    captures = tmp_path / "captures"
    open_path = Path.open

    class BrokenCopy:
        def __init__(self, file):
            self.file = file

        def __enter__(self):
            return self

        def fileno(self):
            return self.file.fileno()

        def write(self, data):
            self.file.write(data[:10] if failure == "write" else data)
            if failure == "write":
                raise OSError("Simulated disk full")

        def __exit__(self, *_args):
            self.file.close()
            if failure == "close":
                raise OSError("Simulated close failure")

    def open_copy(path, *args, **kwargs):
        file = open_path(path, *args, **kwargs)
        return BrokenCopy(file) if path.name.startswith("pack-") else file

    with CardStore(tmp_path / "cards.sqlite3") as store:
        plan = plan_card_import(pack, [1], [], captures)
        monkeypatch.setattr(Path, "open", open_copy)
        with pytest.raises(CardPackError):
            commit_card_import(plan, store, captures)
        assert store.list() == []
        assert not list(captures.iterdir())


def test_duplicate_planning_never_opens_an_external_existing_image(tmp_path, pack, monkeypatch):
    external = tmp_path / "outside.png"
    existing = Card(1, CardKind.IMAGE, "Game", "Map", image_path=str(external))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("An external image was opened during duplicate detection")

    monkeypatch.setattr(Path, "open", forbidden)
    plan = plan_card_import(pack, [1], [existing], tmp_path / "captures")
    assert len(plan.cards) == 1 and plan.duplicates == 0


def test_file_identity_failure_does_not_leave_an_untracked_copy(tmp_path, pack, monkeypatch):
    captures = tmp_path / "captures"
    with CardStore(tmp_path / "cards.sqlite3") as store:
        plan = plan_card_import(pack, [1], [], captures)

        def failed_stat(*_args):
            raise OSError("Simulated fstat failure")

        monkeypatch.setattr(import_module.os, "fstat", failed_stat)
        with pytest.raises(CardPackError):
            commit_card_import(plan, store, captures)
        assert store.list() == [] and not list(captures.iterdir())
