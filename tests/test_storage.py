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

        assert store.delete(card.id)
        assert store.get(card.id) is None
        assert not store.delete(card.id)


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

        assert store.update_favorite(build.id, True)
        assert store.get(build.id).favorite is True
        assert [card.id for card in store.list(query="ROULETTE")] == [puzzle.id]
        assert [card.id for card in store.list(query="elden")] == [build.id]
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

    with CardStore(database) as reopened:
        pinned = reopened.list(pinned_only=True)
        assert len(pinned) == 1
        assert pinned[0].title == "Persistent clue"
        assert pinned[0].pinned is True
        assert (pinned[0].x, pinned[0].y, pinned[0].width, pinned[0].height) == (
            420,
            180,
            480,
            260,
        )
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
        assert store.update_favorite(cards[0].id, True)
        assert store.update_pinned(cards[0].id, True)
