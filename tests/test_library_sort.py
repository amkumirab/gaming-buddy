from __future__ import annotations

import pytest

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


@pytest.mark.parametrize(
    ("sort", "titles"),
    [
        ("default", ["zebra", "Bravo", "alpha"]),
        ("newest", ["alpha", "Bravo", "zebra"]),
        ("oldest", ["zebra", "Bravo", "alpha"]),
        ("title", ["alpha", "Bravo", "zebra"]),
    ],
)
def test_library_sort_orders_cards_without_changing_them(tmp_path, sort, titles):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        for day, title in enumerate(("zebra", "Bravo", "alpha"), start=1):
            store.add(Card(
                None, CardKind.NOTE, "Game", title,
                pinned=day == 1, favorite=day == 2,
                created_at=f"2026-01-{day:02}T12:00:00+00:00",
            ))
        before = store.list()

        assert [card.title for card in store.list(sort=sort)] == titles
        assert store.list() == before
        assert store.list(sort="default") == before


@pytest.mark.parametrize("sort", ["newest", "oldest"])
def test_date_sort_uses_creation_time_not_edits_or_pin_layout(tmp_path, sort):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        old = store.add(Card(
            None, CardKind.NOTE, "Game", "Old", created_at="2026-01-01T12:00:00+00:00",
        ))
        new = store.add(Card(
            None, CardKind.NOTE, "Game", "New", created_at="2026-02-01T12:00:00+00:00",
        ))
        store.update_layout(old.id, x=10, y=20, width=300, height=200, opacity=0.8)
        store.update_details(old.id, title="Edited old", game="Game", content="Clue")
        expected = [new.id, old.id] if sort == "newest" else [old.id, new.id]

        assert [card.id for card in store.list(sort=sort)] == expected


@pytest.mark.parametrize(
    ("sort", "reverse"), [("newest", True), ("oldest", False), ("title", False)],
)
def test_equal_sort_keys_have_a_stable_id_tiebreaker(tmp_path, sort, reverse):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        cards = [store.add(Card(
            None, CardKind.NOTE, "Game", title,
            created_at="2026-01-01T12:00:00+00:00",
        )) for title in ("Clue", "clue", "CLUE")]
        expected = sorted((card.id for card in cards), reverse=reverse)

        assert [card.id for card in store.list(sort=sort)] == expected


@pytest.mark.parametrize("sort", ["default", "newest", "oldest", "title"])
def test_sort_keeps_combined_filters_and_excludes_deleted_cards(tmp_path, sort):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        wanted = store.add(Card(
            None, CardKind.IMAGE, "Game", "Clue", content="door code",
            favorite=True, pinned=True, tags=("puzzle",),
        ))
        for changes in (
            {"game": "Other"}, {"kind": CardKind.NOTE}, {"favorite": False},
            {"pinned": False}, {"tags": ("map",)}, {"content": "unrelated"},
            {},
        ):
            values = {
                "kind": CardKind.IMAGE, "game": "Game", "title": "Other clue",
                "content": "door code", "favorite": True, "pinned": True,
                "tags": ("puzzle",),
            }
            values.update(changes)
            excluded = store.add(Card(None, **values))
            if not changes:
                store.move_to_trash(excluded.id)

        result = store.list("Game", "door code", True, True,
                            kind=CardKind.IMAGE, tag="puzzle", sort=sort)
        assert [card.id for card in result] == [wanted.id]


@pytest.mark.parametrize("value", [None, "", "unknown", "title; DROP TABLE cards; --", [], {}])
def test_invalid_sort_values_fall_back_to_default_without_sql_execution(tmp_path, value):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        store.add(Card(None, CardKind.NOTE, "Game", "Keep me"))
        expected = store.list()

        assert store.list(sort=value) == expected
        assert store.list() == expected


@pytest.mark.parametrize("sort", ["default", "newest", "oldest", "title"])
def test_empty_library_can_be_sorted(tmp_path, sort):
    with CardStore(tmp_path / "cards.sqlite3") as store:
        assert store.list(sort=sort) == []
