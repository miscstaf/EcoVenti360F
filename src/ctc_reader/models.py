from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RegisterDefinition:
    address: int
    key: str
    name: str
    category: str
    signed: bool = True
    scale: float = 1.0
    unit: str = ""
    enum: dict[int, str] = field(default_factory=dict)
    unavailable_raw: frozenset[int] = field(default_factory=frozenset)
    note: str = ""
    word_count: int = 1
    word_order: str = "msw_first"
    encoding: str = "scalar"
    uncertain: bool = False


@dataclass(frozen=True, slots=True)
class ReadResult:
    definition: RegisterDefinition
    raw: int | tuple[int, ...] | None = None
    value: int | float | str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
