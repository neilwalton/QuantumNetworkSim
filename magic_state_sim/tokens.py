"""Token data structures and validation utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from math import isinf
from typing import Any, Iterable, Sequence

from .exceptions import ValidationError

_TOKEN_IDS = count()


def validate_non_negative_int(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{name} must be a non-negative integer")
    return value


def validate_positive_int(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(f"{name} must be a positive integer")
    return value


def validate_probability(value: float, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{name} must be a probability in [0, 1]")
    checked = float(value)
    if not 0 <= checked <= 1:
        raise ValidationError(f"{name} must be a probability in [0, 1]")
    return checked


def validate_positive_number(value: int | float, name: str, *, allow_infinity: bool = False) -> int | float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{name} must be positive")
    checked = float(value)
    if allow_infinity and isinf(checked) and checked > 0:
        return float("inf")
    if checked <= 0 or isinf(checked):
        raise ValidationError(f"{name} must be positive")
    return value


@dataclass
class IdGenerator:
    """Readable monotonic ID generator for simulator objects."""

    prefix: str
    count: int = 0

    def new(self) -> str:
        self.count += 1
        return f"{self.prefix}_{self.count}"


@dataclass
class MagicState:
    """A magic-state token that can be stored, transmitted, and consumed."""

    id: str
    created_at: int
    occupancy: int | float = 1
    fidelity: float | None = None
    flags: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("id must be non-empty")
        validate_non_negative_int(self.created_at, "created_at")
        validate_positive_number(self.occupancy, "occupancy")
        if self.fidelity is not None:
            self.fidelity = validate_probability(self.fidelity, "fidelity")

    def age(self, t: int) -> int:
        validate_non_negative_int(t, "t")
        if t < self.created_at:
            raise ValidationError("t cannot be earlier than created_at")
        return t - self.created_at

    def mark(self, flag: str) -> None:
        self.flags.add(flag)

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags


@dataclass
class BellPair:
    """A Bell-pair token connecting a source memory and target QPU."""

    id: str
    source_id: str
    target_qpu_id: str
    created_at: int
    occupancy: int | float = 1
    fidelity: float | None = None
    flags: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("id must be non-empty")
        if not self.source_id:
            raise ValidationError("source_id must be non-empty")
        if not self.target_qpu_id:
            raise ValidationError("target_qpu_id must be non-empty")
        validate_non_negative_int(self.created_at, "created_at")
        validate_positive_number(self.occupancy, "occupancy")
        if self.fidelity is not None:
            self.fidelity = validate_probability(self.fidelity, "fidelity")

    def age(self, t: int) -> int:
        validate_non_negative_int(t, "t")
        if t < self.created_at:
            raise ValidationError("t cannot be earlier than created_at")
        return t - self.created_at

    def mark(self, flag: str) -> None:
        self.flags.add(flag)

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags


class MagicStateToken(MagicState):
    """Backward-compatible token wrapper used by the original small API."""

    def __init__(
        self,
        produced_at: int,
        fidelity: float = 1.0,
        source: str = "factory",
        token_id: int | None = None,
        occupancy: int | float = 1,
    ) -> None:
        validate_non_negative_int(produced_at, "produced_at")
        if not source:
            raise ValidationError("source must be non-empty")
        assigned_token_id = next(_TOKEN_IDS) if token_id is None else token_id
        super().__init__(
            id=f"token_{assigned_token_id}",
            created_at=produced_at,
            occupancy=occupancy,
            fidelity=fidelity,
            metadata={"source": source, "token_id": assigned_token_id},
        )

    @property
    def produced_at(self) -> int:
        return self.created_at

    @property
    def source(self) -> str:
        return str(self.metadata.get("source", "factory"))

    @property
    def token_id(self) -> int:
        return int(self.metadata["token_id"])

    @property
    def age(self) -> int:
        """Compatibility property; use ``age_at`` or ``age(t)`` for real age."""
        return 0

    def age_at(self, time: int) -> int:
        return MagicState.age(self, time)


@dataclass(frozen=True)
class TokenBatch:
    """A lightweight immutable batch of magic-state tokens."""

    tokens: tuple[MagicState, ...]

    def __init__(self, tokens: Iterable[MagicState] = ()) -> None:
        object.__setattr__(self, "tokens", tuple(tokens))
        if not all(isinstance(token, MagicState) for token in self.tokens):
            raise ValidationError("TokenBatch accepts only MagicState instances")

    def __len__(self) -> int:
        return len(self.tokens)

    def __iter__(self):
        return iter(self.tokens)

    def __bool__(self) -> bool:
        return bool(self.tokens)

    def take(self, count: int) -> tuple[tuple[MagicState, ...], "TokenBatch"]:
        validate_non_negative_int(count, "count")
        return self.tokens[:count], TokenBatch(self.tokens[count:])


def ensure_tokens(tokens: Sequence[MagicState], minimum: int = 0) -> tuple[MagicState, ...]:
    validate_non_negative_int(minimum, "minimum")
    checked = tuple(tokens)
    if not all(isinstance(token, MagicState) for token in checked):
        raise ValidationError("expected MagicState instances")
    if len(checked) < minimum:
        raise ValidationError(f"expected at least {minimum} tokens")
    return checked
