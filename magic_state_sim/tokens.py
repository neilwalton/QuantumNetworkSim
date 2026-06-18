"""Token data structures and validation utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Iterable, Sequence

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
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
        raise ValidationError(f"{name} must be a probability in [0, 1]")
    return float(value)


@dataclass(frozen=True, slots=True)
class MagicStateToken:
    """A produced magic-state token that can be stored, transmitted, and consumed."""

    produced_at: int
    fidelity: float = 1.0
    source: str = "factory"
    token_id: int = field(default_factory=lambda: next(_TOKEN_IDS))

    def __post_init__(self) -> None:
        validate_non_negative_int(self.produced_at, "produced_at")
        validate_probability(self.fidelity, "fidelity")
        if not self.source:
            raise ValidationError("source must be non-empty")

    @property
    def age(self) -> int:
        """Age is context-dependent; use ``age_at`` for simulation time."""
        return 0

    def age_at(self, time: int) -> int:
        validate_non_negative_int(time, "time")
        if time < self.produced_at:
            raise ValidationError("time cannot be earlier than produced_at")
        return time - self.produced_at


@dataclass(frozen=True, slots=True)
class TokenBatch:
    """A lightweight immutable batch of magic-state tokens."""

    tokens: tuple[MagicStateToken, ...]

    def __init__(self, tokens: Iterable[MagicStateToken] = ()) -> None:
        object.__setattr__(self, "tokens", tuple(tokens))
        if not all(isinstance(token, MagicStateToken) for token in self.tokens):
            raise ValidationError("TokenBatch accepts only MagicStateToken instances")

    def __len__(self) -> int: return len(self.tokens)
    def __iter__(self): return iter(self.tokens)
    def __bool__(self) -> bool: return bool(self.tokens)

    def take(self, count: int) -> tuple[tuple[MagicStateToken, ...], "TokenBatch"]:
        validate_non_negative_int(count, "count")
        return self.tokens[:count], TokenBatch(self.tokens[count:])


def ensure_tokens(tokens: Sequence[MagicStateToken], minimum: int = 0) -> tuple[MagicStateToken, ...]:
    validate_non_negative_int(minimum, "minimum")
    checked = tuple(tokens)
    if not all(isinstance(token, MagicStateToken) for token in checked):
        raise ValidationError("expected MagicStateToken instances")
    if len(checked) < minimum:
        raise ValidationError(f"expected at least {minimum} tokens")
    return checked
