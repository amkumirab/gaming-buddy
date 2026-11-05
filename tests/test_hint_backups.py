import hashlib
import json
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QSettings

from gaming_buddy.hint_cards import HintContent
from gaming_buddy.models import Card, CardKind
from gaming_buddy.storage import CardStore
from gaming_buddy.workspace_backup import (
    BackupError,
    create_workspace_backup,
    inspect_workspace_backup,
    restore_workspace_backup,
)


def test_backup_preserves_hint_progress_but_does_not_overwrite_existing_progress(tmp_path):
    path = tmp_path / "workspace.zip"
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    with CardStore(tmp_path / "source.sqlite3") as source:
        source.add(Card(None, CardKind.NOTE, "Game", "Guide",
                        hints=HintContent(("a", "b", "c"), 2)))
        create_workspace_backup(path, source, settings)
    with ZipFile(path) as archive:
        assert json.loads(archive.read("manifest.json"))["version"] == 3
    with CardStore(tmp_path / "destination.sqlite3") as destination:
        result = restore_workspace_backup(path, destination, tmp_path / "captures", settings)
        assert result.imported_cards == 1
        restored = destination.list()[0]
        assert restored.hints.revealed == 2
        assert destination.set_hint_progress(restored.id, restored.hints, 0)
        result = restore_workspace_backup(path, destination, tmp_path / "captures", settings)
        assert result.duplicate_cards == 1 and result.imported_cards == 0
        assert destination.get(restored.id).hints.revealed == 0


@pytest.mark.parametrize("problem", ["downgrade", "content", "progress"])
def test_invalid_hints_fail_backup_inspection_instead_of_being_silently_dropped(tmp_path, problem):
    path = tmp_path / "workspace.zip"
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    with CardStore(tmp_path / "source.sqlite3") as source:
        source.add(Card(None, CardKind.NOTE, "Game", "Guide", hints=HintContent(("a", "b", "c"))))
        create_workspace_backup(path, source, settings)
    with ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    records = json.loads(files["cards.json"])
    if problem == "downgrade":
        manifest["version"] = 2
    elif problem == "content":
        records[0]["content"] = "Unstructured spoiler"
    else:
        records[0]["hints"]["revealed"] = True
    files["cards.json"] = json.dumps(records).encode()
    manifest["checksums"]["cards.json"] = hashlib.sha256(files["cards.json"]).hexdigest()
    files["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(path, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    with pytest.raises(BackupError, match="invalid hint card"):
        inspect_workspace_backup(path)
