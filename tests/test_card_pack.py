from __future__ import annotations

import io
import json
import stat
import struct
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from PySide6.QtGui import QColor, QImage

import gaming_buddy.card_pack as pack_module
from gaming_buddy.card_export import create_card_export
from gaming_buddy.card_pack import CardPackError, load_card_pack
from gaming_buddy.models import Card, CardKind


def test_image_preview_is_bounded_without_changing_original_bytes(tmp_path):
    path = tmp_path / "wide.png"
    image = QImage(2400, 600, QImage.Format.Format_RGB32)
    image.fill(QColor("purple"))
    assert image.save(str(path))
    archive = tmp_path / "wide.zip"
    create_card_export(archive, [Card(None, CardKind.IMAGE, "Game", "Map", image_path=str(path))])
    loaded = load_card_pack(archive).cards[0].image
    assert loaded.data == path.read_bytes()
    preview = QImage.fromData(loaded.preview)
    assert not preview.isNull()
    assert preview.width() <= 1024 and preview.height() <= 180


def make_export(tmp_path):
    image = QImage(20, 10, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    source = tmp_path / "original.png"
    assert image.save(str(source))
    destination = tmp_path / "cards.zip"
    create_card_export(destination, [
        Card(None, CardKind.NOTE, "Game", "Door clue", content="First line\n\nLast line",
             tags=("puzzle",), favorite=True),
        Card(None, CardKind.IMAGE, "Game", "Map", image_path=str(source)),
        Card(None, CardKind.IMAGE, "Game", "Missing", image_path=str(tmp_path / "missing.png")),
    ])
    return destination, source


def test_export_round_trip_is_read_only_and_preserves_original_bytes(tmp_path):
    destination, source = make_export(tmp_path)
    before = set(tmp_path.iterdir())
    pack = load_card_pack(destination)

    assert len(pack.cards) == 3
    assert pack.cards[0].content == "First line\n\nLast line"
    assert pack.cards[0].tags == ("puzzle",)
    assert pack.cards[0].favorite
    assert pack.cards[1].image.data == source.read_bytes()
    assert pack.cards[1].available
    assert not pack.cards[2].available
    assert set(tmp_path.iterdir()) == before
    destination.write_bytes(b"changed after preview")
    assert pack.cards[1].image.data == source.read_bytes()


@pytest.mark.parametrize("name", ["../outside.png", "/absolute.png", "C:/drive.png",
                                  "images\\bad.png", "images/../bad.png", "run.exe"])
def test_unsafe_or_unknown_archive_members_are_rejected(tmp_path, name):
    destination = tmp_path / "unsafe.zip"
    with ZipFile(destination, "w") as archive:
        archive.writestr("cards.json", json.dumps({
            "format": "gaming-buddy-cards", "version": 1, "cards": [],
        }))
        archive.writestr(name, b"untrusted")
    with pytest.raises(CardPackError):
        load_card_pack(destination)


def write_pack(path, manifest, members=()):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("cards.json", json.dumps(manifest))
        for name, data in members:
            archive.writestr(name, data)


def note_manifest():
    return {"format": "gaming-buddy-cards", "version": 1,
            "cards": [{"kind": "note", "title": "Clue", "content": "Keep me"}]}


@pytest.mark.parametrize("field,value", [
    ("kind", "executable"), ("title", []), ("title", ""), ("title", "Bad\x00title"),
    ("game", "g" * 161), ("content", "\x00"), ("content", "x" * 200_001),
    ("tags", "puzzle"), ("tags", [3]), ("tags", ["x" * 29]),
    ("tags", ["\ud800"]), ("favorite", "true"), ("created_at", "tomorrow"),
    ("created_at", "2026-01-01"), ("image", "https://example.test/map.png"),
    ("image_available", False),
], ids=lambda value: repr(value)[:45])
def test_malformed_card_metadata_is_rejected(tmp_path, field, value):
    manifest = note_manifest()
    manifest["cards"][0][field] = value
    source = tmp_path / "bad.zip"
    write_pack(source, manifest)
    with pytest.raises(CardPackError):
        load_card_pack(source)


@pytest.mark.parametrize("field,value", [
    ("version", True), ("version", 2), ("format", "gaming-buddy-workspace"),
    ("cards", []), ("cards", {}), ("cards", [None]),
])
def test_unsupported_manifest_is_rejected(tmp_path, field, value):
    manifest = note_manifest()
    manifest[field] = value
    source = tmp_path / "bad.zip"
    write_pack(source, manifest)
    with pytest.raises(CardPackError):
        load_card_pack(source)


@pytest.mark.parametrize("member", ["CARDS.JSON", "images/a.png"])
def test_ambiguous_names_and_unreferenced_images_are_rejected(tmp_path, member):
    source = tmp_path / "bad.zip"
    write_pack(source, note_manifest(), [(member, b"not an image")])
    with pytest.raises(CardPackError):
        load_card_pack(source)


def test_nul_in_original_filename_is_rejected_before_zipinfo_truncates_it(tmp_path):
    source = tmp_path / "nul.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("cards.jsonXhidden", json.dumps(note_manifest()))
    source.write_bytes(source.read_bytes().replace(b"cards.jsonXhidden", b"cards.json\x00hidden"))
    with pytest.raises(CardPackError):
        load_card_pack(source)


def test_symlink_is_rejected(tmp_path):
    info = ZipInfo("images/link.png")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    source = tmp_path / "bad.zip"
    write_pack(source, note_manifest(), [(info, b"../../outside")])
    with pytest.raises(CardPackError):
        load_card_pack(source)


@pytest.mark.parametrize("payload", [b'{"format":1,"format":2}', b'{"cards": NaN}', b'\xff'])
def test_ambiguous_or_invalid_json_is_rejected(tmp_path, payload):
    source = tmp_path / "bad.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("cards.json", payload)
    with pytest.raises(CardPackError):
        load_card_pack(source)


def test_directory_is_bounded_before_zipfile_construction_even_if_count_lies(tmp_path, monkeypatch):
    source = tmp_path / "many.zip"
    write_pack(source, note_manifest(), [("README.md", b"index"), ("images/a.png", b"x")])
    data = bytearray(source.read_bytes())
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", data, end + 8, 1, 1)  # The directory actually has three records.
    source.write_bytes(data)
    monkeypatch.setattr(pack_module, "MAX_MEMBERS", 2)

    def forbidden(*_args):
        raise AssertionError("ZipFile was constructed before directory limits were checked")

    monkeypatch.setattr(pack_module, "ZipFile", forbidden)
    with pytest.raises(CardPackError):
        load_card_pack(source)


@pytest.mark.parametrize("limit", ["MAX_PACK_BYTES", "MAX_TOTAL_BYTES", "MAX_JSON_BYTES",
                                  "MAX_DIRECTORY_BYTES", "MAX_CARDS"])
def test_archive_and_metadata_limits_are_enforced(tmp_path, monkeypatch, limit):
    source, _image = make_export(tmp_path)
    monkeypatch.setattr(pack_module, limit, 1)
    with pytest.raises(CardPackError):
        load_card_pack(source)


@pytest.mark.parametrize("limit", ["MAX_IMAGE_BYTES", "MAX_IMAGE_PIXELS", "MAX_TOTAL_PIXELS"])
def test_image_limits_are_enforced_before_import(tmp_path, monkeypatch, limit):
    source, _image = make_export(tmp_path)
    monkeypatch.setattr(pack_module, limit, 1)
    with pytest.raises(CardPackError):
        load_card_pack(source)


def test_corrupt_image_is_rejected(tmp_path):
    manifest = note_manifest()
    manifest["cards"][0].update(kind="image", image="images/map.png", image_available=True)
    source = tmp_path / "bad.zip"
    write_pack(source, manifest, [("images/map.png", b"not a PNG")])
    with pytest.raises(CardPackError):
        load_card_pack(source)


def test_cancelled_read_does_not_open_source(tmp_path):
    with pytest.raises(CardPackError, match="cancelled"):
        load_card_pack(tmp_path / "not-opened.zip", cancelled=lambda: True)


def test_hidden_zip64_directory_cannot_bypass_member_preflight(tmp_path, monkeypatch):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("a", b"")
    raw = stream.getvalue()
    end = raw.rfind(b"PK\x05\x06")
    offset = struct.unpack_from("<L", raw, end + 16)[0]
    base = raw[offset:end]
    hidden = base * 2000
    final = bytearray(base)
    struct.pack_into("<H", final, 32, 76)
    trailer = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44, 45, 45, 0, 0,
                          2001, 2001, len(hidden) + len(final), 0)
    trailer += struct.pack("<4sLQL", b"PK\x06\x07", 0, 0, 1)
    eocd = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1,
                       len(final) + len(trailer), len(hidden), 0)
    source = tmp_path / "hidden.zip"
    source.write_bytes(hidden + final + trailer + eocd)

    def forbidden(*_args):
        raise AssertionError("ZIP64 redirected eager parsing to the hidden directory")

    monkeypatch.setattr(pack_module, "ZipFile", forbidden)
    with pytest.raises(CardPackError):
        load_card_pack(source)
