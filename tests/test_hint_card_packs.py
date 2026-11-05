import json
from zipfile import ZipFile

import pytest

from gaming_buddy.card_export import create_card_export
from gaming_buddy.card_pack import CardPackError, load_card_pack
from gaming_buddy.card_pack_dialog import CardPackDialog
from gaming_buddy.card_pack_import import commit_card_import, plan_card_import
from gaming_buddy.hint_cards import HintContent
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore


def test_shared_hints_start_hidden_and_duplicate_import_keeps_progress(tmp_path):
    card = Card(None, CardKind.NOTE, "Game", "Gate guide",
                hints=HintContent(("Look around", "Check the wall", "SPOILER-0451"), 2))
    path = tmp_path / "hints.zip"
    create_card_export(path, [card])
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read("cards.json"))
        assert manifest["version"] == 2
        assert manifest["cards"][0]["hints"]["revealed"] == 0
        readme = archive.read("README.md").decode()
        assert all(step not in readme for step in card.hints.steps)
    pack = load_card_pack(path)
    assert pack.cards[0].hints == card.hints.with_progress(0)
    with CardStore(tmp_path / "cards.sqlite3") as store:
        captures = tmp_path / "captures"
        commit_card_import(plan_card_import(pack, [0], [], captures), store, captures)
        imported = store.list()[0]
        assert store.set_hint_progress(imported.id, imported.hints, 1)
        again = commit_card_import(plan_card_import(pack, [0], store.list(), captures), store,
                                   captures)
        assert again.imported == 0 and again.duplicates == 1
        assert store.get(imported.id).hints.revealed == 1


@pytest.mark.parametrize("version,content,progress", [(1, "", 0), (2, "leak", 0), (2, "", 4)])
def test_invalid_or_downgraded_shared_hints_are_rejected(tmp_path, version, content, progress):
    path = tmp_path / "bad.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("cards.json", json.dumps({
            "format": "gaming-buddy-cards", "version": version, "cards": [{
                "kind": "note", "title": "Guide", "content": content,
                "hints": {"steps": ["a", "b", "c"], "revealed": progress},
            }],
        }))
    with pytest.raises(CardPackError):
        load_card_pack(path)


def test_import_preview_never_displays_even_previously_revealed_stages(tmp_path, qt_application):
    path = tmp_path / "guide.zip"
    create_card_export(path, [Card(None, CardKind.NOTE, "Game", "Guide",
                                   hints=HintContent(("SUBTLE", "GUIDANCE", "SECRET"), 3))])
    # An incoming pack may claim fully revealed progress; the reader still resets it.
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read("cards.json"))
    manifest["cards"][0]["hints"]["revealed"] = 3
    with ZipFile(path, "w") as archive:
        archive.writestr("cards.json", json.dumps(manifest))
    pack = load_card_pack(path)
    assert pack.cards[0].hints.revealed == 0
    dialog = CardPackDialog(path, [], tmp_path / "captures", [])
    dialog._autostart.stop()
    dialog._pack = pack
    dialog._populate()
    assert all(step not in dialog.note_preview.toPlainText() for step in pack.cards[0].hints.steps)
    assert "hidden" in dialog.note_preview.toPlainText()
    dialog.reject()
    dialog.deleteLater()
