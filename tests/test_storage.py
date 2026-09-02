import sqlite3

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


def test_card_lifecycle(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="Control",
                title="Luck puzzle",
                content="Try the roulette wheel.",
            )
        )

        assert card.id is not None
        assert store.get(card.id) == card
        assert store.list("Control") == [card]
        assert store.list("Another game") == []

        store.update_layout(
            card.id,
            x=15,
            y=25,
            width=500,
            height=260,
            opacity=0.55,
        )
        updated = store.get(card.id)
        assert updated is not None
        assert (updated.x, updated.y, updated.width, updated.height) == (15, 25, 500, 260)
        assert updated.opacity == 0.55

        assert store.move_to_trash(card.id)
        assert store.get(card.id) is None
        assert store.list() == []
        deleted = store.get_deleted(card.id)
        assert deleted is not None
        assert deleted.pinned is False
        assert deleted.deleted_at
        assert not store.move_to_trash(card.id)

        assert store.restore(card.id)
        restored = store.get(card.id)
        assert restored is not None
        assert restored.title == card.title
        assert restored.deleted_at == ""
        assert not store.restore(card.id)

        assert not store.delete_permanently(card.id)
        assert store.move_to_trash(card.id)
        assert store.delete_permanently(card.id)
        assert store.get_deleted(card.id) is None


def test_values_are_safely_clamped(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="",
                title="Tiny",
                content="Test",
                opacity=4,
                width=1,
                height=1,
            )
        )
        loaded = store.get(card.id)
        assert loaded is not None
        assert loaded.opacity == 1.0
        assert loaded.width == 160
        assert loaded.height == 100


def test_card_details_can_be_edited_without_losing_workspace_state(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="Control",
                title="Original clue",
                content="Old text",
                favorite=True,
                pinned=True,
                x=240,
                y=160,
            )
        )

        assert store.update_details(
            card.id,
            title="  Updated clue  ",
            game="  Alan Wake 2  ",
            content="New text",
        )
        updated = store.get(card.id)
        assert updated is not None
        assert (updated.title, updated.game, updated.content) == (
            "Updated clue",
            "Alan Wake 2",
            "New text",
        )
        assert updated.favorite is True
        assert updated.pinned is True
        assert (updated.x, updated.y) == (240, 160)
        assert not store.update_details(9999, title="Missing", game="Game", content="")


def test_list_returns_most_recent_first(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        first = store.add(
            Card(id=None, kind=CardKind.NOTE, game="Game", title="First", content="1")
        )
        second = store.add(
            Card(id=None, kind=CardKind.NOTE, game="Game", title="Second", content="2")
        )

        assert [card.id for card in store.list()] == [second.id, first.id]


def test_search_and_favorite_filters(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        puzzle = store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="Control",
                title="Luck puzzle",
                content="Try the roulette wheel.",
            )
        )
        build = store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="Elden Ring",
                title="Strength build",
                content="Upgrade the greatsword.",
            )
        )
        screenshot = store.add(
            Card(
                id=None,
                kind=CardKind.IMAGE,
                game="Resident Evil 2",
                title="West office safe",
                content="Left 9, right 15, left 7",
                image_path=str(tmp_path / "safe.png"),
            )
        )

        assert store.update_favorite(build.id, True)
        assert store.get(build.id).favorite is True
        assert [card.id for card in store.list(query="ROULETTE")] == [puzzle.id]
        assert [card.id for card in store.list(query="elden")] == [build.id]
        assert [card.id for card in store.list(query="right 15")] == [screenshot.id]
        assert [card.id for card in store.list(favorites_only=True)] == [build.id]
        assert store.list("Control", "strength") == []


def test_pinned_workspace_survives_database_reopen(tmp_path):
    database = tmp_path / "cards.sqlite3"
    with CardStore(database) as store:
        card = store.add(
            Card(
                id=None,
                kind=CardKind.NOTE,
                game="Game",
                title="Persistent clue",
                content="Restore this pin",
                x=420,
                y=180,
                width=480,
                height=260,
            )
        )
        assert store.update_pinned(card.id, True)
        assert store.update_locked(card.id, True)
        assert store.update_collapsed(card.id, True)

    with CardStore(database) as reopened:
        pinned = reopened.list(pinned_only=True)
        assert len(pinned) == 1
        assert pinned[0].title == "Persistent clue"
        assert pinned[0].pinned is True
        assert pinned[0].locked is True
        assert pinned[0].collapsed is True
        assert (pinned[0].x, pinned[0].y, pinned[0].width, pinned[0].height) == (
            420,
            180,
            480,
            260,
        )
        assert reopened.unlock_all_pins() == 1
        assert reopened.get(pinned[0].id).locked is False
        assert reopened.set_all_pins_collapsed(False) == 1
        assert reopened.get(pinned[0].id).collapsed is False
        assert reopened.update_pinned(pinned[0].id, False)
        assert reopened.list(pinned_only=True) == []
        assert len(reopened.list()) == 1


def test_existing_database_gets_workspace_columns(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            game TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            image_path TEXT NOT NULL DEFAULT '',
            opacity REAL NOT NULL DEFAULT 0.88,
            x INTEGER NOT NULL DEFAULT 80,
            y INTEGER NOT NULL DEFAULT 80,
            width INTEGER NOT NULL DEFAULT 320,
            height INTEGER NOT NULL DEFAULT 220,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO cards (kind, game, title, content, created_at, updated_at)
        VALUES ('note', 'Legacy Game', 'Old clue', 'Keep me', '2026-01-01', '2026-01-01')
        """
    )
    connection.commit()
    connection.close()

    with CardStore(database) as store:
        cards = store.list()
        assert len(cards) == 1
        assert cards[0].title == "Old clue"
        assert cards[0].favorite is False
        assert cards[0].pinned is False
        assert cards[0].locked is False
        assert cards[0].collapsed is False
        assert cards[0].deleted_at == ""
        assert store.update_favorite(cards[0].id, True)
        assert store.update_pinned(cards[0].id, True)
        assert store.update_locked(cards[0].id, True)
        assert store.update_collapsed(cards[0].id, True)


def test_bulk_collapse_only_changes_pinned_cards(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        pinned = store.add(Card(None, CardKind.NOTE, "Game", "Pinned"))
        library_card = store.add(Card(None, CardKind.NOTE, "Game", "Library"))
        assert store.update_pinned(pinned.id, True)
        assert store.update_collapsed(library_card.id, True)

        assert store.set_all_pins_collapsed(True) == 1
        assert store.get(pinned.id).collapsed is True
        assert store.get(library_card.id).collapsed is True

        assert store.set_all_pins_collapsed(False) == 1
        assert store.get(pinned.id).collapsed is False
        assert store.get(library_card.id).collapsed is True


def test_deleted_cards_can_be_searched_and_purged_by_age(tmp_path):
    database = tmp_path / "cards.sqlite3"
    with CardStore(database) as store:
        old = store.add(Card(None, CardKind.NOTE, "Control", "Old clue", content="Oceanview"))
        recent = store.add(
            Card(None, CardKind.NOTE, "Alan Wake 2", "Recent clue", content="Coffee World")
        )
        assert store.move_to_trash(old.id)
        assert store.move_to_trash(recent.id)

        connection = sqlite3.connect(database)
        connection.execute(
            "UPDATE cards SET deleted_at = ? WHERE id = ?",
            ("2026-01-01T00:00:00+00:00", old.id),
        )
        connection.execute(
            "UPDATE cards SET deleted_at = ? WHERE id = ?",
            ("2026-08-20T00:00:00+00:00", recent.id),
        )
        connection.commit()
        connection.close()

        assert [card.id for card in store.list_deleted("coffee")] == [recent.id]
        purged = store.purge_deleted_before("2026-08-01T00:00:00+00:00")
        assert [card.id for card in purged] == [old.id]
        assert store.get_deleted(old.id) is None
        assert store.get_deleted(recent.id) is not None
        assert store.deleted_count() == 1


def test_empty_trash_returns_removed_cards(tmp_path):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        first = store.add(Card(None, CardKind.NOTE, "Game", "First"))
        second = store.add(Card(None, CardKind.NOTE, "Game", "Second"))
        assert store.move_to_trash(first.id)
        assert store.move_to_trash(second.id)

        removed = store.empty_trash()

        assert {card.id for card in removed} == {first.id, second.id}
        assert store.deleted_count() == 0
