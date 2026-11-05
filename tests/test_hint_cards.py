import sqlite3

import pytest

from gaming_buddy.hint_cards import HintContent
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


def test_hint_progress_is_atomic_persistent_and_not_searchable(tmp_path):
    path = tmp_path / "cards.sqlite3"
    hints = HintContent(("Look east", "Find the red door", "Secret answer 0451"))
    with CardStore(path) as store:
        card = store.add(Card(None, CardKind.NOTE, "Puzzle", "Gate guide", hints=hints))
        assert store.get(card.id).hints == hints
        assert not store.list(query="0451")
        assert store.list(query="Gate")[0].id == card.id
        assert store.set_hint_progress(card.id, hints, 1)
        assert not store.set_hint_progress(card.id, hints, 2)
        assert store.get(card.id).hints.revealed == 1
        store.move_to_trash(card.id)
        assert not store.set_hint_progress(card.id, hints.with_progress(1), 2)
        store.restore(card.id)
    with CardStore(path) as reopened:
        assert reopened.get(card.id).hints.revealed == 1
        assert not reopened.list(query="Secret answer")


def test_stale_hint_update_cannot_reveal_new_content(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        old = HintContent(("A", "B", "C"))
        card = store.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=old))
        new = HintContent(("New clue", "More", "Answer"))
        assert store.update_hint_details(card.id, title="Guide", game="Game", tags=(), hints=new)
        assert not store.set_hint_progress(card.id, old, 1)
        assert store.get(card.id).hints == new
        assert not store.update_note_content(card.id, expected="", content="Unsafe checklist")
        with pytest.raises(ValueError):
            store.update_details(card.id, title="Guide", game="Game", content="Unsafe plain text")


def test_hint_creation_rolls_back_if_structured_data_cannot_be_written(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        store._connection.execute(
            "CREATE TRIGGER reject_hints BEFORE INSERT ON card_hints "
            "BEGIN SELECT RAISE(ABORT, 'controlled failure'); END"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            store.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=HintContent(("a", "b", "c"))))
        assert not store.list()


def test_hint_edit_is_atomic_and_metadata_only_changes_keep_progress(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        hints = HintContent(("a", "b", "c"), 2)
        card = store.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=hints, tags=("old",)))
        store.update_hint_details(card.id, title="Renamed", game="Other", tags=("new",), hints=hints)
        before = store.get(card.id)
        assert before.hints == hints
        store._connection.execute(
            "CREATE TRIGGER reject_hint_edit BEFORE UPDATE ON card_hints "
            "BEGIN SELECT RAISE(ABORT, 'controlled failure'); END"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.Error):
            store.update_hint_details(card.id, title="Lost", game="Elsewhere", tags=("lost",),
                                      hints=HintContent(("changed", "b", "c")))
        assert store.get(card.id) == before


def test_progress_rolls_back_if_card_timestamp_write_fails(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        hints = HintContent(("a", "b", "c"))
        card = store.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=hints))
        store._connection.execute(
            "CREATE TRIGGER reject_timestamp BEFORE UPDATE OF updated_at ON cards "
            "BEGIN SELECT RAISE(ABORT, 'controlled failure'); END"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.Error):
            store.set_hint_progress(card.id, hints, 1)
        assert store.get(card.id).hints == hints


def test_legacy_notes_survive_schema_upgrade_and_hint_deletion_cascades(tmp_path):
    path = tmp_path / "cards.sqlite3"
    with CardStore(path) as store:
        note = store.add(Card(None, CardKind.NOTE, "Game", "Existing", content="a\n\nb\n"))
        store._connection.execute("DROP TABLE card_hints")
        store._connection.commit()
    with CardStore(path) as store:
        assert store.get(note.id) == note
        hints = HintContent(("a", "b", "c"))
        card = store.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=hints))
        store.move_to_trash(card.id)
        assert store.get_deleted(card.id).hints == hints
        assert not store.list_deleted("c")
        store.delete_permanently(card.id)
        assert store._connection.execute("SELECT count(*) FROM card_hints").fetchone()[0] == 0


@pytest.mark.parametrize("steps,progress", [((), 0), (("a", "b", ""), 0), (("a", "b", "c"), 4),
                                           (("a", "b", "c"), True)])
def test_hint_validation_rejects_invalid_payload(steps, progress):
    with pytest.raises(ValueError):
        HintContent(steps, progress)
