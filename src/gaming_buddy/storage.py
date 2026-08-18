from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Self

from gaming_buddy.models import Card, CardKind, utc_now


class CardStore:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self._connection = sqlite3.connect(database)
        self._connection.row_factory = sqlite3.Row
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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_game_updated ON cards(game, updated_at DESC)"
        )
        self._connection.commit()

    def add(self, card: Card) -> Card:
        card.with_timestamps()
        cursor = self._connection.execute(
            """
            INSERT INTO cards (
                kind, game, title, content, image_path, opacity,
                x, y, width, height, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                card.created_at,
                card.updated_at,
            ),
        )
        self._connection.commit()
        card.id = int(cursor.lastrowid)
        return card

    def list(self, game: str | None = None) -> list[Card]:
        if game is None or not game.strip():
            rows = self._connection.execute(
                "SELECT * FROM cards ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM cards WHERE game = ? ORDER BY updated_at DESC, id DESC",
                (game.strip(),),
            ).fetchall()
        return [self._row_to_card(row) for row in rows]

    def get(self, card_id: int) -> Card | None:
        row = self._connection.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return self._row_to_card(row) if row else None

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
            WHERE id = ?
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

    def delete(self, card_id: int) -> bool:
        cursor = self._connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        self._connection.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> Card:
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
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
