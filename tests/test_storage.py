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
