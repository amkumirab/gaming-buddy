import sqlite3

import pytest

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


def test_failed_tag_write_rolls_back_card_edit_and_does_not_leak_into_later_commit(tmp_path):
    database = tmp_path / "cards.sqlite3"
    with CardStore(database) as store:
        card = store.add(Card(None, CardKind.NOTE, "Puzzle", "Old title", content="Old clue",
                              tags=("original",)))
        # A real SQLite constraint fails after UPDATE and the old tags' DELETE.
        store._connection.execute(
            "CREATE TRIGGER reject_tag BEFORE INSERT ON card_tags "
            "WHEN NEW.tag = 'rejected' BEGIN SELECT RAISE(ABORT, 'controlled tag failure'); END"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.IntegrityError, match="controlled tag failure"):
            store.update_details(card.id, title="New title", game="Another game", content="New clue",
                                 tags=("rejected",))
        stored = store.get(card.id)
        assert (stored.title, stored.game, stored.content, stored.tags) == (
            "Old title", "Puzzle", "Old clue", ("original",),
        )
        store.add(Card(None, CardKind.NOTE, "General", "Unrelated note"))
    with CardStore(database) as reopened:
        assert reopened.get(card.id).content == "Old clue"
        assert reopened.get(card.id).tags == ("original",)
