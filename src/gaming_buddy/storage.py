from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Self

from gaming_buddy.models import Card, CardKind, utc_now
from gaming_buddy.tags import normalize_tags
from gaming_buddy.workspace_presets import (
    PresetPinLayout,
    WorkspacePreset,
    WorkspacePresetSummary,
    normalize_preset_name,
)


class CardStore:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._connection = sqlite3.connect(database)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('note', 'image')),
                game TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                image_path TEXT NOT NULL DEFAULT '',
                opacity REAL NOT NULL DEFAULT 0.88,
                x INTEGER NOT NULL DEFAULT 80,
                y INTEGER NOT NULL DEFAULT 80,
                width INTEGER NOT NULL DEFAULT 320,
                height INTEGER NOT NULL DEFAULT 220,
                favorite INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0,
                collapsed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        columns = {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(cards)").fetchall()
        }
        if "favorite" not in columns:
            self._connection.execute(
                "ALTER TABLE cards ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
            )
        if "pinned" not in columns:
            self._connection.execute(
                "ALTER TABLE cards ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
            )
        if "locked" not in columns:
            self._connection.execute(
                "ALTER TABLE cards ADD COLUMN locked INTEGER NOT NULL DEFAULT 0"
            )
        if "collapsed" not in columns:
            self._connection.execute(
                "ALTER TABLE cards ADD COLUMN collapsed INTEGER NOT NULL DEFAULT 0"
            )
        if "deleted_at" not in columns:
            self._connection.execute(
                "ALTER TABLE cards ADD COLUMN deleted_at TEXT NOT NULL DEFAULT ''"
            )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS card_tags (
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                tag TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (card_id, tag)
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_card_tags_tag ON card_tags(tag COLLATE NOCASE)"
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game TEXT NOT NULL COLLATE NOCASE,
                name TEXT NOT NULL COLLATE NOCASE,
                active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (game, name)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_preset_pins (
                preset_id INTEGER NOT NULL
                    REFERENCES workspace_presets(id) ON DELETE CASCADE,
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                visible INTEGER NOT NULL DEFAULT 1,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                opacity REAL NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0,
                collapsed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (preset_id, card_id)
            )
            """
        )
        self._connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_presets_active_game
            ON workspace_presets(game COLLATE NOCASE) WHERE active = 1
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_game_updated ON cards(game, updated_at DESC)"
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cards_favorite_updated
            ON cards(favorite DESC, updated_at DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cards_pinned_updated
            ON cards(pinned DESC, updated_at DESC)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cards_deleted_at
            ON cards(deleted_at DESC)
            """
        )
        self._connection.commit()

    def add(self, card: Card) -> Card:
        card.with_timestamps()
        cursor = self._connection.execute(
            """
            INSERT INTO cards (
                kind, game, title, content, image_path, opacity,
                x, y, width, height, favorite, pinned, locked, collapsed,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card.kind.value,
                card.game.strip(),
                card.title.strip(),
                card.content,
                card.image_path,
                min(1.0, max(0.2, card.opacity)),
                card.x,
                card.y,
                max(160, card.width),
                max(100, card.height),
                int(card.favorite),
                int(card.pinned),
                int(card.locked),
                int(card.collapsed),
                card.created_at,
                card.updated_at,
            ),
        )
        card.id = int(cursor.lastrowid)
        card.tags = normalize_tags(card.tags)
        self._replace_tags(card.id, card.tags)
        self._connection.commit()
        return card

    def list(
        self,
        game: str | None = None,
        query: str | None = None,
        favorites_only: bool = False,
        pinned_only: bool = False,
        *,
        kind: CardKind | None = None,
        tag: str | None = None,
    ) -> list[Card]:
        clauses: list[str] = ["deleted_at = ''"]
        parameters: list[object] = []
        if game is not None and game.strip():
            clauses.append("game = ?")
            parameters.append(game.strip())
        if query is not None and query.strip():
            pattern = f"%{query.strip()}%"
            clauses.append(
                """
                (title LIKE ? COLLATE NOCASE
                 OR content LIKE ? COLLATE NOCASE
                 OR game LIKE ? COLLATE NOCASE
                 OR EXISTS (
                     SELECT 1 FROM card_tags
                     WHERE card_id = cards.id AND tag LIKE ? COLLATE NOCASE
                 ))
                """
            )
            parameters.extend((pattern, pattern, pattern, pattern))
        if favorites_only:
            clauses.append("favorite = 1")
        if pinned_only:
            clauses.append("pinned = 1")
        if kind is not None:
            clauses.append("kind = ?")
            parameters.append(kind.value)
        if tag is not None and tag.strip():
            clauses.append(
                "EXISTS (SELECT 1 FROM card_tags WHERE card_id = cards.id AND tag = ? COLLATE NOCASE)"
            )
            parameters.append(tag.strip())

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"""
            SELECT * FROM cards{where}
            ORDER BY pinned DESC, favorite DESC, updated_at DESC, id DESC
            """,
            parameters,
        ).fetchall()
        return self._cards_from_rows(rows)

    def get(self, card_id: int) -> Card | None:
        row = self._connection.execute(
            "SELECT * FROM cards WHERE id = ? AND deleted_at = ''", (card_id,)
        ).fetchone()
        return self._row_to_card(row, self._tags_for_card(int(row["id"]))) if row else None

    def get_deleted(self, card_id: int) -> Card | None:
        row = self._connection.execute(
            "SELECT * FROM cards WHERE id = ? AND deleted_at != ''", (card_id,)
        ).fetchone()
        return self._row_to_card(row, self._tags_for_card(int(row["id"]))) if row else None

    def list_deleted(self, query: str | None = None) -> list[Card]:
        parameters: list[object] = []
        search = ""
        if query is not None and query.strip():
            pattern = f"%{query.strip()}%"
            search = """
                AND (title LIKE ? COLLATE NOCASE
                     OR content LIKE ? COLLATE NOCASE
                     OR game LIKE ? COLLATE NOCASE
                     OR EXISTS (
                         SELECT 1 FROM card_tags
                         WHERE card_id = cards.id AND tag LIKE ? COLLATE NOCASE
                     ))
            """
            parameters.extend((pattern, pattern, pattern, pattern))
        rows = self._connection.execute(
            f"""
            SELECT * FROM cards
            WHERE deleted_at != ''{search}
            ORDER BY deleted_at DESC, id DESC
            """,
            parameters,
        ).fetchall()
        return self._cards_from_rows(rows)

    def deleted_count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS total FROM cards WHERE deleted_at != ''"
        ).fetchone()
        return int(row["total"])

    def update_layout(
        self,
        card_id: int,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        opacity: float,
    ) -> None:
        self._connection.execute(
            """
            UPDATE cards
            SET x = ?, y = ?, width = ?, height = ?, opacity = ?, updated_at = ?
            WHERE id = ? AND deleted_at = ''
            """,
            (
                x,
                y,
                max(160, width),
                max(100, height),
                min(1.0, max(0.2, opacity)),
                utc_now(),
                card_id,
            ),
        )
        self._connection.commit()

    def update_favorite(self, card_id: int, favorite: bool) -> bool:
        cursor = self._connection.execute(
            "UPDATE cards SET favorite = ?, updated_at = ? WHERE id = ? AND deleted_at = ''",
            (int(favorite), utc_now(), card_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def update_pinned(self, card_id: int, pinned: bool) -> bool:
        cursor = self._connection.execute(
            "UPDATE cards SET pinned = ?, updated_at = ? WHERE id = ? AND deleted_at = ''",
            (int(pinned), utc_now(), card_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def update_locked(self, card_id: int, locked: bool) -> bool:
        cursor = self._connection.execute(
            "UPDATE cards SET locked = ?, updated_at = ? WHERE id = ? AND deleted_at = ''",
            (int(locked), utc_now(), card_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def unlock_all_pins(self) -> int:
        cursor = self._connection.execute(
            """
            UPDATE cards
            SET locked = 0, updated_at = ?
            WHERE pinned = 1 AND locked = 1 AND deleted_at = ''
            """,
            (utc_now(),),
        )
        self._connection.commit()
        return cursor.rowcount

    def update_collapsed(self, card_id: int, collapsed: bool) -> bool:
        cursor = self._connection.execute(
            "UPDATE cards SET collapsed = ?, updated_at = ? "
            "WHERE id = ? AND deleted_at = ''",
            (int(collapsed), utc_now(), card_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def set_all_pins_collapsed(self, collapsed: bool) -> int:
        cursor = self._connection.execute(
            """
            UPDATE cards
            SET collapsed = ?, updated_at = ?
            WHERE pinned = 1 AND collapsed != ? AND deleted_at = ''
            """,
            (int(collapsed), utc_now(), int(collapsed)),
        )
        self._connection.commit()
        return cursor.rowcount

    def update_details(
        self,
        card_id: int,
        *,
        title: str,
        game: str,
        content: str,
        tags: Sequence[str] | None = None,
    ) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE cards
            SET title = ?, game = ?, content = ?, updated_at = ?
            WHERE id = ? AND deleted_at = ''
            """,
            (title.strip(), game.strip(), content, utc_now(), card_id),
        )
        if cursor.rowcount > 0 and tags is not None:
            self._replace_tags(card_id, tags)
        self._connection.commit()
        return cursor.rowcount > 0

    def save_workspace_preset(
        self,
        game: str,
        name: str,
        pins: Sequence[PresetPinLayout],
        *,
        activate: bool = True,
    ) -> WorkspacePreset:
        game = game.strip() or "General"
        name = normalize_preset_name(name)
        now = utc_now()
        with self._connection:
            if activate:
                self._connection.execute(
                    "UPDATE workspace_presets SET active = 0 WHERE game = ? COLLATE NOCASE",
                    (game,),
                )
                conflict_update = "active = 1, updated_at = excluded.updated_at"
            else:
                conflict_update = "updated_at = excluded.updated_at"
            self._connection.execute(
                f"""
                INSERT INTO workspace_presets (
                    game, name, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(game, name) DO UPDATE SET {conflict_update}
                """,
                (game, name, int(activate), now, now),
            )
            row = self._connection.execute(
                """
                SELECT id FROM workspace_presets
                WHERE game = ? COLLATE NOCASE AND name = ? COLLATE NOCASE
                """,
                (game, name),
            ).fetchone()
            preset_id = int(row["id"])
            self._connection.execute(
                "DELETE FROM workspace_preset_pins WHERE preset_id = ?",
                (preset_id,),
            )
            self._connection.executemany(
                """
                INSERT INTO workspace_preset_pins (
                    preset_id, card_id, visible, x, y, width, height,
                    opacity, locked, collapsed
                )
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                WHERE EXISTS (
                    SELECT 1 FROM cards WHERE id = ? AND deleted_at = ''
                )
                """,
                (
                    (
                        preset_id,
                        pin.card_id,
                        int(pin.visible),
                        pin.x,
                        pin.y,
                        max(160, pin.width),
                        max(100, pin.height),
                        min(1.0, max(0.2, pin.opacity)),
                        int(pin.locked),
                        int(pin.collapsed),
                        pin.card_id,
                    )
                    for pin in pins
                ),
            )
        preset = self.get_workspace_preset(preset_id)
        if preset is None:  # pragma: no cover - guarded by the transaction above
            raise RuntimeError("The saved layout could not be loaded.")
        return preset

    def list_workspace_presets(self, game: str) -> list[WorkspacePresetSummary]:
        rows = self._connection.execute(
            """
            SELECT
                workspace_presets.*,
                COUNT(cards.id) AS pin_count
            FROM workspace_presets
            LEFT JOIN workspace_preset_pins
                ON workspace_preset_pins.preset_id = workspace_presets.id
            LEFT JOIN cards
                ON cards.id = workspace_preset_pins.card_id
                AND cards.deleted_at = ''
            WHERE workspace_presets.game = ? COLLATE NOCASE
            GROUP BY workspace_presets.id
            ORDER BY workspace_presets.active DESC,
                     workspace_presets.name COLLATE NOCASE
            """,
            (game.strip() or "General",),
        ).fetchall()
        return [self._row_to_workspace_preset_summary(row) for row in rows]

    def all_workspace_presets(self) -> list[WorkspacePreset]:
        rows = self._connection.execute(
            "SELECT id FROM workspace_presets ORDER BY game COLLATE NOCASE, name COLLATE NOCASE"
        ).fetchall()
        return [
            preset
            for row in rows
            if (preset := self.get_workspace_preset(int(row["id"]))) is not None
        ]

    def get_workspace_preset(self, preset_id: int) -> WorkspacePreset | None:
        row = self._connection.execute(
            "SELECT * FROM workspace_presets WHERE id = ?",
            (preset_id,),
        ).fetchone()
        if row is None:
            return None
        pin_rows = self._connection.execute(
            """
            SELECT workspace_preset_pins.*
            FROM workspace_preset_pins
            JOIN cards ON cards.id = workspace_preset_pins.card_id
            WHERE workspace_preset_pins.preset_id = ? AND cards.deleted_at = ''
            ORDER BY workspace_preset_pins.card_id
            """,
            (preset_id,),
        ).fetchall()
        return WorkspacePreset(
            id=int(row["id"]),
            game=str(row["game"]),
            name=str(row["name"]),
            pins=tuple(self._row_to_preset_pin(pin_row) for pin_row in pin_rows),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def active_workspace_preset(self, game: str) -> WorkspacePreset | None:
        row = self._connection.execute(
            """
            SELECT id FROM workspace_presets
            WHERE game = ? COLLATE NOCASE AND active = 1
            """,
            (game.strip() or "General",),
        ).fetchone()
        return self.get_workspace_preset(int(row["id"])) if row is not None else None

    def workspace_preset_named(self, game: str, name: str) -> WorkspacePreset | None:
        try:
            name = normalize_preset_name(name)
        except ValueError:
            return None
        row = self._connection.execute(
            """
            SELECT id FROM workspace_presets
            WHERE game = ? COLLATE NOCASE AND name = ? COLLATE NOCASE
            """,
            (game.strip() or "General", name),
        ).fetchone()
        return self.get_workspace_preset(int(row["id"])) if row is not None else None

    def rename_workspace_preset(self, preset_id: int, name: str) -> bool:
        name = normalize_preset_name(name)
        try:
            cursor = self._connection.execute(
                "UPDATE workspace_presets SET name = ?, updated_at = ? WHERE id = ?",
                (name, utc_now(), preset_id),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("A layout with that name already exists for this game.") from exc
        return cursor.rowcount > 0

    def delete_workspace_preset(self, preset_id: int) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM workspace_presets WHERE id = ?",
            (preset_id,),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def activate_workspace_preset(self, preset_id: int) -> bool:
        row = self._connection.execute(
            "SELECT game FROM workspace_presets WHERE id = ?",
            (preset_id,),
        ).fetchone()
        if row is None:
            return False
        with self._connection:
            self._connection.execute(
                "UPDATE workspace_presets SET active = 0 WHERE game = ? COLLATE NOCASE",
                (str(row["game"]),),
            )
            cursor = self._connection.execute(
                "UPDATE workspace_presets SET active = 1 WHERE id = ?",
                (preset_id,),
            )
        return cursor.rowcount > 0

    def apply_workspace_preset(self, preset_id: int) -> WorkspacePreset | None:
        preset = self.get_workspace_preset(preset_id)
        if preset is None:
            return None
        now = utc_now()
        with self._connection:
            self._connection.execute(
                "UPDATE workspace_presets SET active = 0 WHERE game = ? COLLATE NOCASE",
                (preset.game,),
            )
            self._connection.execute(
                "UPDATE workspace_presets SET active = 1, updated_at = ? WHERE id = ?",
                (now, preset.id),
            )
            self._connection.executemany(
                """
                UPDATE cards SET
                    pinned = 1, x = ?, y = ?, width = ?, height = ?, opacity = ?,
                    locked = ?, collapsed = ?, updated_at = ?
                WHERE id = ? AND deleted_at = ''
                """,
                (
                    (
                        pin.x,
                        pin.y,
                        max(160, pin.width),
                        max(100, pin.height),
                        min(1.0, max(0.2, pin.opacity)),
                        int(pin.locked),
                        int(pin.collapsed),
                        now,
                        pin.card_id,
                    )
                    for pin in preset.pins
                ),
            )
        return self.get_workspace_preset(preset.id)

    @staticmethod
    def _row_to_workspace_preset_summary(row: sqlite3.Row) -> WorkspacePresetSummary:
        return WorkspacePresetSummary(
            id=int(row["id"]),
            game=str(row["game"]),
            name=str(row["name"]),
            pin_count=int(row["pin_count"]),
            active=bool(row["active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_preset_pin(row: sqlite3.Row) -> PresetPinLayout:
        return PresetPinLayout(
            card_id=int(row["card_id"]),
            visible=bool(row["visible"]),
            x=int(row["x"]),
            y=int(row["y"]),
            width=int(row["width"]),
            height=int(row["height"]),
            opacity=float(row["opacity"]),
            locked=bool(row["locked"]),
            collapsed=bool(row["collapsed"]),
        )

    def update_tags(self, card_id: int, tags: Sequence[str]) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM cards WHERE id = ? AND deleted_at = ''",
            (card_id,),
        ).fetchone()
        if row is None:
            return False
        self._replace_tags(card_id, tags)
        self._connection.commit()
        return True

    def available_tags(self, game: str | None = None) -> list[str]:
        parameters: list[object] = []
        game_filter = ""
        if game is not None and game.strip():
            game_filter = " AND cards.game = ?"
            parameters.append(game.strip())
        rows = self._connection.execute(
            f"""
            SELECT card_tags.tag, COUNT(*) AS uses
            FROM card_tags
            JOIN cards ON cards.id = card_tags.card_id
            WHERE cards.deleted_at = ''{game_filter}
            GROUP BY card_tags.tag COLLATE NOCASE
            ORDER BY uses DESC, card_tags.tag COLLATE NOCASE
            """,
            parameters,
        ).fetchall()
        return [str(row["tag"]) for row in rows]

    def move_to_trash(self, card_id: int) -> bool:
        now = utc_now()
        cursor = self._connection.execute(
            """
            UPDATE cards
            SET pinned = 0, deleted_at = ?, updated_at = ?
            WHERE id = ? AND deleted_at = ''
            """,
            (now, now, card_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def restore(self, card_id: int) -> bool:
        cursor = self._connection.execute(
            """
            UPDATE cards
            SET deleted_at = '', updated_at = ?
            WHERE id = ? AND deleted_at != ''
            """,
            (utc_now(), card_id),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def delete_permanently(self, card_id: int) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM cards WHERE id = ? AND deleted_at != ''", (card_id,)
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def empty_trash(self) -> list[Card]:
        cards = self.list_deleted()
        self._connection.execute("DELETE FROM cards WHERE deleted_at != ''")
        self._connection.commit()
        return cards

    def purge_deleted_before(self, cutoff: str) -> list[Card]:
        rows = self._connection.execute(
            "SELECT * FROM cards WHERE deleted_at != '' AND deleted_at < ?",
            (cutoff,),
        ).fetchall()
        cards = self._cards_from_rows(rows)
        if not cards:
            return []
        self._connection.executemany(
            "DELETE FROM cards WHERE id = ? AND deleted_at != ''",
            ((card.id,) for card in cards),
        )
        self._connection.commit()
        return cards

    def image_path_is_referenced(self, image_path: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM cards WHERE image_path = ? LIMIT 1", (image_path,)
        ).fetchone()
        return row is not None

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _cards_from_rows(self, rows: Sequence[sqlite3.Row]) -> list[Card]:
        if not rows:
            return []
        card_ids = [int(row["id"]) for row in rows]
        tags_by_card: dict[int, list[str]] = {card_id: [] for card_id in card_ids}
        for start in range(0, len(card_ids), 900):
            chunk = card_ids[start : start + 900]
            placeholders = ",".join("?" for _ in chunk)
            tag_rows = self._connection.execute(
                f"""
                SELECT card_id, tag FROM card_tags
                WHERE card_id IN ({placeholders})
                ORDER BY tag COLLATE NOCASE
                """,
                chunk,
            ).fetchall()
            for tag_row in tag_rows:
                tags_by_card[int(tag_row["card_id"])].append(str(tag_row["tag"]))
        return [
            self._row_to_card(row, tuple(tags_by_card[int(row["id"])])) for row in rows
        ]

    def _tags_for_card(self, card_id: int) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT tag FROM card_tags WHERE card_id = ? ORDER BY tag COLLATE NOCASE",
            (card_id,),
        ).fetchall()
        return tuple(str(row["tag"]) for row in rows)

    def _replace_tags(self, card_id: int, tags: Sequence[str]) -> None:
        normalized = normalize_tags(tags)
        self._connection.execute("DELETE FROM card_tags WHERE card_id = ?", (card_id,))
        self._connection.executemany(
            "INSERT INTO card_tags (card_id, tag) VALUES (?, ?)",
            ((card_id, tag) for tag in normalized),
        )

    @staticmethod
    def _row_to_card(row: sqlite3.Row, tags: tuple[str, ...] = ()) -> Card:
        return Card(
            id=int(row["id"]),
            kind=CardKind(row["kind"]),
            game=str(row["game"]),
            title=str(row["title"]),
            content=str(row["content"]),
            image_path=str(row["image_path"]),
            opacity=float(row["opacity"]),
            x=int(row["x"]),
            y=int(row["y"]),
            width=int(row["width"]),
            height=int(row["height"]),
            favorite=bool(row["favorite"]),
            pinned=bool(row["pinned"]),
            locked=bool(row["locked"]),
            collapsed=bool(row["collapsed"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            deleted_at=str(row["deleted_at"]),
            tags=tags,
        )
