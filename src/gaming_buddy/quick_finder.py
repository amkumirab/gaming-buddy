from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gaming_buddy.models import Card, CardKind
from gaming_buddy.tags import format_tags

MAX_RECENT_SEARCHES = 5


def find_cards(cards: Sequence[Card], query: str, active_game: str = "") -> list[Card]:
    terms = [term for term in query.casefold().split() if term]
    active = active_game.strip().casefold()
    matches: list[tuple[int, Card]] = []
    for index, card in enumerate(cards):
        title = card.title.casefold()
        game = card.game.casefold()
        content = card.content.casefold()
        tags = " ".join(card.tags).casefold()
        combined = f"{title} {game} {content} {tags}"
        if terms and not all(term in combined for term in terms):
            continue
        matches.append((index, card))

    query_text = query.strip().casefold()

    def rank(entry: tuple[int, Card]) -> tuple[int, int, int, int, int]:
        index, card = entry
        game = card.game.strip().casefold()
        if active and game == active:
            game_rank = 0
        elif active and game == "general":
            game_rank = 1
        else:
            game_rank = 2

        title = card.title.casefold()
        card_game = card.game.casefold()
        if not query_text:
            match_rank = 4
        elif title == query_text:
            match_rank = 0
        elif title.startswith(query_text):
            match_rank = 1
        elif query_text in title:
            match_rank = 2
        elif query_text in card_game:
            match_rank = 3
        else:
            match_rank = 4
        return game_rank, match_rank, not card.pinned, not card.favorite, index

    return [card for _, card in sorted(matches, key=rank)]


def card_statuses(card: Card) -> list[str]:
    statuses = ["Image" if card.kind is CardKind.IMAGE else "Note"]
    if card.pinned:
        statuses.append("Pinned")
        if card.locked:
            statuses.append("Locked")
        if card.collapsed:
            statuses.append("Collapsed")
    return statuses


def updated_search_history(
    history: Sequence[str],
    query: str,
    *,
    limit: int = MAX_RECENT_SEARCHES,
) -> list[str]:
    cleaned = query.strip()
    if limit <= 0:
        return []
    candidates = ([cleaned] if cleaned else []) + [
        item.strip() for item in history if item.strip()
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = item.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(item)
    return unique[:limit]


class QuickFinderDialog(QDialog):
    card_activated = Signal(object, str)

    def __init__(
        self,
        cards: Sequence[Card],
        active_game: str = "",
        recent_searches: Sequence[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cards = list(cards)
        self._cards_by_id = {card.id: card for card in cards if card.id is not None}
        self._active_game = active_game.strip()

        self.setWindowTitle("Quick card finder")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(520, 390)
        self.resize(600, 470)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Find a saved card")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        context = QLabel(
            f"Results for {self._active_game} appear first."
            if self._active_game
            else "Search titles, note text, and game names."
        )
        context.setObjectName("muted")
        layout.addWidget(context)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a title, clue, code, or game…")
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        self.search.textChanged.connect(self._refresh_results)
        self.search.returnPressed.connect(self._activate_current)
        search_row.addWidget(self.search, 1)

        self.recent = QComboBox()
        self.recent.setMinimumWidth(150)
        self.recent.setMaximumWidth(190)
        self.recent.addItem("Recent searches")
        for query in recent_searches[:MAX_RECENT_SEARCHES]:
            if query.strip():
                self.recent.addItem(query.strip())
        self.recent.currentIndexChanged.connect(self._use_recent_search)
        self.recent.setVisible(self.recent.count() > 1)
        search_row.addWidget(self.recent)
        layout.addLayout(search_row)

        self.results = QListWidget()
        self.results.itemActivated.connect(lambda _item: self._activate_current())
        layout.addWidget(self.results, 1)

        footer = QHBoxLayout()
        self.result_count = QLabel()
        self.result_count.setObjectName("muted")
        controls = QLabel("↑↓ select  ·  Enter show  ·  Esc close")
        controls.setObjectName("muted")
        footer.addWidget(self.result_count)
        footer.addStretch(1)
        footer.addWidget(controls)
        layout.addLayout(footer)
        self._refresh_results()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        screen = self.screen()
        cursor_screen = QGuiApplication.screenAt(QCursor.pos())
        if cursor_screen is not None:
            screen = cursor_screen
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center() - self.rect().center())
        self.search.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.search.selectAll()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched is self.search and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent) and key_event.key() in (
                Qt.Key.Key_Down,
                Qt.Key.Key_Up,
            ):
                if self.results.count():
                    row = self.results.currentRow()
                    step = 1 if key_event.key() == Qt.Key.Key_Down else -1
                    self.results.setCurrentRow(max(0, min(self.results.count() - 1, row + step)))
                    self.results.setFocus(Qt.FocusReason.ShortcutFocusReason)
                return True
        return super().eventFilter(watched, event)

    def _use_recent_search(self, index: int) -> None:
        if index <= 0:
            return
        self.search.setText(self.recent.itemText(index))
        self.search.setFocus(Qt.FocusReason.OtherFocusReason)
        self.search.selectAll()
        self.recent.setCurrentIndex(0)

    def _refresh_results(self) -> None:
        self.results.clear()
        matches = find_cards(self._cards, self.search.text(), self._active_game)
        for card in matches:
            favorite = "★ " if card.favorite else ""
            kind = "▣" if card.kind is CardKind.IMAGE else "◆"
            details = " · ".join((card.game or "General", *card_statuses(card)))
            tags = format_tags(card.tags)
            if tags:
                details = f"{details} · {tags}"
            item = QListWidgetItem(f"{favorite}{kind}  {card.title}\n     {details}")
            item.setData(Qt.ItemDataRole.UserRole, card.id)
            if card.kind is CardKind.NOTE:
                tooltip = card.content
            elif card.content.strip():
                tooltip = f"{card.content}\n\nFile: {card.image_path}"
            else:
                tooltip = card.image_path
            item.setToolTip(tooltip[:400])
            self.results.addItem(item)
        if matches:
            self.results.setCurrentRow(0)
        noun = "card" if len(matches) == 1 else "cards"
        self.result_count.setText(f"{len(matches)} {noun}")

    def _activate_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        card = self._cards_by_id.get(item.data(Qt.ItemDataRole.UserRole))
        if card is None:
            return
        self.card_activated.emit(card, self.search.text().strip())
        self.accept()
