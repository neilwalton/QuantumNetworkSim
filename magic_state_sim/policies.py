"""Drop, selection, routing, and compatibility policies."""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Sequence

from .tokens import MagicState, validate_positive_int


class DropPolicy:
    """Select one stored object to drop."""

    def select(self, states: Sequence[object], *, t: int, rng):
        raise NotImplementedError


class DropLowestFidelityPolicy(DropPolicy):
    def select(self, states: Sequence[object], *, t: int, rng):
        candidates = [s for s in states if getattr(s, "fidelity", None) is not None]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.fidelity)


class DropOldestPolicy(DropPolicy):
    def select(self, states: Sequence[object], *, t: int, rng):
        candidates = [s for s in states if hasattr(s, "created_at")]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.created_at)


class DropRandomPolicy(DropPolicy):
    def select(self, states: Sequence[object], *, t: int, rng):
        if not states:
            return None
        return rng.choice(list(states))


class DefaultDropPolicy(DropPolicy):
    """Drop lowest fidelity, then oldest, then random."""

    def select(self, states: Sequence[object], *, t: int, rng):
        if not states:
            return None
        by_fidelity = DropLowestFidelityPolicy().select(states, t=t, rng=rng)
        if by_fidelity is not None:
            return by_fidelity
        by_age = DropOldestPolicy().select(states, t=t, rng=rng)
        if by_age is not None:
            return by_age
        return DropRandomPolicy().select(states, t=t, rng=rng)


class MagicStateSelectionPolicy:
    """Select available magic states for transmission."""

    def select(self, states: Sequence[MagicState], n: int, *, t: int, rng) -> list[MagicState]:
        raise NotImplementedError


class OldestFirstSelectionPolicy(MagicStateSelectionPolicy):
    def select(self, states: Sequence[MagicState], n: int, *, t: int, rng) -> list[MagicState]:
        return list(sorted(states, key=lambda s: s.created_at)[:n])


class StoragePolicy:
    """Compatibility admission policy for the original simulator API."""

    def admit(self, tokens, memory, time: int):
        return tuple(tokens)


@dataclass
class DropNewestOnOverflow(StoragePolicy):
    def admit(self, tokens, memory, time: int):
        tokens = tuple(tokens)
        capacity = getattr(memory, "remaining_capacity", 0)
        return tokens[: int(capacity)]


@dataclass
class DropOldestOnOverflow(StoragePolicy):
    def admit(self, tokens, memory, time: int):
        tokens = tuple(tokens)
        overflow = max(0, len(tokens) - int(getattr(memory, "remaining_capacity", 0)))
        if overflow and hasattr(memory, "discard_oldest"):
            memory.discard_oldest(overflow)
        return tokens[: int(getattr(memory, "remaining_capacity", 0))]


class RoutingPolicy:
    def select_destination(self, destinations, token: MagicState, time: int):
        return destinations[0] if destinations else None


class RoundRobinRoutingPolicy(RoutingPolicy):
    def __init__(self) -> None:
        self._index = 0

    def select_destination(self, destinations, token, time: int):
        if not destinations:
            return None
        dest = destinations[self._index % len(destinations)]
        self._index += 1
        return dest


@dataclass
class RandomRoutingPolicy(RoutingPolicy):
    seed: int | None = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def select_destination(self, destinations, token, time: int):
        return self._rng.choice(list(destinations)) if destinations else None


@dataclass
class ConsumptionPolicy:
    tokens_per_operation: int = 1

    def __post_init__(self) -> None:
        validate_positive_int(self.tokens_per_operation, "tokens_per_operation")
