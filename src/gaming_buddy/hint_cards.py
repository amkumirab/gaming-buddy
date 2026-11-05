from __future__ import annotations

from dataclasses import dataclass, replace

STAGE_LABELS = ("Subtle hint", "More guidance", "Full solution")
MAX_HINT_LENGTH = 30_000


@dataclass(frozen=True, slots=True)
class HintContent:
    steps: tuple[str, str, str]
    revealed: int = 0

    def __post_init__(self) -> None:
        if (not isinstance(self.steps, tuple) or len(self.steps) != 3
                or type(self.revealed) is not int or not 0 <= self.revealed <= 3):
            raise ValueError("A hint card needs three stages and valid progress.")
        for text in self.steps:
            if (not isinstance(text, str) or not text.strip() or len(text) > MAX_HINT_LENGTH
                    or any(ord(char) < 32 and char not in "\n\r\t" for char in text)):
                raise ValueError("Each hint stage needs valid text within the length limit.")
            try:
                text.encode("utf-8")
            except UnicodeError as error:
                raise ValueError("A hint stage contains invalid text.") from error

    def with_progress(self, progress: int) -> HintContent:
        return replace(self, revealed=progress)

    @property
    def visible_text(self) -> str:
        return "\n\n".join(f"{STAGE_LABELS[index]}\n{text}"
                            for index, text in enumerate(self.steps[:self.revealed]))

    def to_record(self, *, share: bool = False) -> dict:
        return {"steps": list(self.steps), "revealed": 0 if share else self.revealed}

    @classmethod
    def from_record(cls, record: object, *, share: bool = False) -> HintContent:
        if (not isinstance(record, dict) or set(record) != {"steps", "revealed"}
                or not isinstance(record["steps"], list)):
            raise ValueError("Invalid hint card metadata.")
        result = cls(tuple(record["steps"]), record["revealed"])
        return result.with_progress(0) if share else result
