import pytest

from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore
from gaming_buddy.workspace_presets import PresetPinLayout, normalize_preset_name


def _layout(card_id: int, *, visible: bool = True, x: int = 20) -> PresetPinLayout:
    return PresetPinLayout(
        card_id=card_id,
        visible=visible,
        x=x,
        y=40,
        width=420,
        height=240,
        opacity=0.65,
        locked=True,
        collapsed=True,
    )


def test_layout_names_are_normalized_and_validated() -> None:
    assert normalize_preset_name("  Boss   fight  ") == "Boss fight"
    with pytest.raises(ValueError, match="Enter a layout name"):
        normalize_preset_name("   ")
    with pytest.raises(ValueError, match="up to 48"):
        normalize_preset_name("x" * 49)


def test_presets_save_activate_apply_rename_and_delete(tmp_path) -> None:
    database = tmp_path / "cards.sqlite3"
    with CardStore(database) as store:
        first = store.add(
            Card(None, CardKind.NOTE, "Control", "Clue", pinned=True)
        )
        second = store.add(
            Card(None, CardKind.NOTE, "General", "Shared", pinned=True)
        )
        assert first.id is not None and second.id is not None

        exploration = store.save_workspace_preset(
            "Control",
            "  Exploration  ",
            (_layout(first.id), _layout(second.id, visible=False, x=500)),
        )
        assert exploration.name == "Exploration"
        assert exploration.active is True
        assert len(exploration.pins) == 2

        combat = store.save_workspace_preset(
            "control",
            "Combat",
            (_layout(first.id, x=900),),
        )
        summaries = store.list_workspace_presets("CONTROL")
        assert [summary.name for summary in summaries] == ["Combat", "Exploration"]
        assert [summary.active for summary in summaries] == [True, False]
        assert [summary.pin_count for summary in summaries] == [1, 2]

        applied = store.apply_workspace_preset(exploration.id)
        assert applied is not None and applied.active is True
        restored = store.get(first.id)
        assert restored is not None
        assert (restored.x, restored.y, restored.width, restored.height) == (20, 40, 420, 240)
        assert restored.opacity == 0.65
        assert restored.locked is True
        assert restored.collapsed is True
        assert store.active_workspace_preset("Control").id == exploration.id

        assert store.rename_workspace_preset(combat.id, "Boss fight")
        with pytest.raises(ValueError, match="already exists"):
            store.rename_workspace_preset(combat.id, "exploration")
        assert store.delete_workspace_preset(combat.id)
        assert store.get(first.id) is not None

    with CardStore(database) as reopened:
        persisted = reopened.workspace_preset_named("control", "EXPLORATION")
        assert persisted is not None
        assert persisted.id == exploration.id


def test_saving_same_case_insensitive_name_replaces_pin_layout(tmp_path) -> None:
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(Card(None, CardKind.NOTE, "Game", "Card", pinned=True))
        assert card.id is not None
        first = store.save_workspace_preset("Game", "Desk", (_layout(card.id, x=10),))
        replaced = store.save_workspace_preset("game", "desk", (_layout(card.id, x=700),))

        assert replaced.id == first.id
        assert len(store.list_workspace_presets("Game")) == 1
        assert replaced.pins[0].x == 700


def test_deleting_a_card_removes_it_from_saved_layouts(tmp_path) -> None:
    with CardStore(tmp_path / "cards.sqlite3") as store:
        card = store.add(Card(None, CardKind.NOTE, "Game", "Card", pinned=True))
        assert card.id is not None
        preset = store.save_workspace_preset("Game", "Only", (_layout(card.id),))

        assert store.move_to_trash(card.id)
        assert store.get_workspace_preset(preset.id).pins == ()
        assert store.delete_permanently(card.id)
        assert store.list_workspace_presets("Game")[0].pin_count == 0
