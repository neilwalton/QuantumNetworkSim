"""Finite magic-state memory models."""
from __future__ import annotations

from dataclasses import dataclass, field

from .exceptions import InsufficientTokensError, MemoryFullError
from .policies import DefaultDropPolicy, DropPolicy, MagicStateSelectionPolicy, OldestFirstSelectionPolicy
from .tokens import MagicState, validate_positive_number, validate_probability


@dataclass(init=False)
class FiniteMemory:
    """A finite memory with capacity measured by total magic-state occupancy."""

    capacity: int | float
    id: str = "memory"
    decoherence_probability: float = 0.0
    drop_policy: DropPolicy | None = None
    selection_policy: MagicStateSelectionPolicy | None = None
    _contents: list[MagicState] = field(default_factory=list, init=False, repr=False)

    def __init__(
        self,
        *args,
        id: str | None = None,
        capacity: int | float | None = None,
        decoherence_probability: float = 0.0,
        drop_policy: DropPolicy | None = None,
        selection_policy: MagicStateSelectionPolicy | None = None,
    ) -> None:
        if args:
            if isinstance(args[0], str):
                id = args[0]
                if len(args) > 1:
                    capacity = args[1]
            else:
                capacity = args[0]
                if len(args) > 1:
                    id = args[1]
            if len(args) > 2:
                raise TypeError("FiniteMemory accepts at most two positional arguments")
        if capacity is None:
            raise TypeError("capacity is required")
        self.id = id or "memory"
        self.capacity = capacity
        self.decoherence_probability = decoherence_probability
        self.drop_policy = drop_policy
        self.selection_policy = selection_policy
        self._contents = []
        self.__post_init__()

    def __post_init__(self) -> None:
        self.drop_policy = self.drop_policy or DefaultDropPolicy()
        self.selection_policy = self.selection_policy or OldestFirstSelectionPolicy()
        self.validate()

    def validate(self) -> None:
        if not self.id:
            raise ValueError("id must be non-empty")
        self.capacity = validate_positive_number(self.capacity, "capacity", allow_infinity=True)
        self.decoherence_probability = validate_probability(
            self.decoherence_probability, "decoherence_probability"
        )

    def __len__(self) -> int:
        return len(self._contents)

    @property
    def available(self) -> int:
        return len(self._contents)

    @property
    def remaining_capacity(self) -> int | float:
        return self.capacity - self.occupancy()

    def list(self) -> list[MagicState]:
        return list(self._contents)

    def peek(self) -> tuple[MagicState, ...]:
        return tuple(self._contents)

    def clear(self) -> None:
        self._contents.clear()

    def occupancy(self) -> int | float:
        return sum(state.occupancy for state in self._contents)

    def add(self, state, t: int = 0, rng=None) -> bool | int:
        if isinstance(state, (list, tuple)):
            return self._add_compat_many(state, t=t, rng=rng)
        return self._add_one(state, t=t, rng=rng)

    def _add_compat_many(self, states, t: int, rng) -> int:
        states = tuple(states)
        if sum(state.occupancy for state in states) > self.remaining_capacity:
            raise MemoryFullError("memory capacity exceeded")
        for state in states:
            self._contents.append(state)
            state.mark("in_memory")
        return len(states)

    def _add_one(self, state: MagicState, t: int, rng=None) -> bool:
        if state.occupancy > self.capacity:
            state.mark("rejected_too_large")
            return False
        while self.occupancy() + state.occupancy > self.capacity:
            victim = self.drop_policy.select(self._contents, t=t, rng=rng)
            if victim is None:
                state.mark("rejected_no_drop_candidate")
                return False
            self._contents.remove(victim)
            victim.mark("dropped")
        self._contents.append(state)
        state.mark("in_memory")
        return True

    def add_many(self, states: list[MagicState], t: int, rng=None) -> list[MagicState]:
        accepted: list[MagicState] = []
        for state in states:
            if self._add_one(state, t=t, rng=rng):
                accepted.append(state)
        return accepted

    def pop_by_id(self, state_id: str) -> MagicState | None:
        for state in list(self._contents):
            if state.id == state_id:
                self._contents.remove(state)
                state.flags.discard("in_memory")
                return state
        return None

    def pop_available(self, n: int, t: int = 0, policy: MagicStateSelectionPolicy | None = None) -> list[MagicState]:
        if n <= 0:
            return []
        selected = (policy or self.selection_policy).select(self._contents, n, t=t, rng=None)
        popped: list[MagicState] = []
        for state in selected:
            if state in self._contents:
                self._contents.remove(state)
                state.flags.discard("in_memory")
                popped.append(state)
        return popped

    def take(self, count: int = 1) -> tuple[MagicState, ...]:
        if len(self._contents) < count:
            raise InsufficientTokensError("not enough tokens in memory")
        return tuple(self.pop_available(count))

    def discard_oldest(self, count: int = 1) -> tuple[MagicState, ...]:
        removed = tuple(self.pop_available(count))
        for state in removed:
            state.mark("dropped")
        return removed

    def step(self, t: int, rng) -> None:
        survivors: list[MagicState] = []
        for state in self._contents:
            if rng.random() < self.decoherence_probability:
                state.mark("decohered")
            else:
                survivors.append(state)
        self._contents = survivors
        self.enforce_capacity(t=t, rng=rng)

    def enforce_capacity(self, t: int = 0, rng=None) -> None:
        while self.occupancy() > self.capacity and self._contents:
            victim = self.drop_policy.select(self._contents, t=t, rng=rng)
            if victim is None:
                break
            self._contents.remove(victim)
            victim.mark("dropped")

    def update_params(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.validate()
        self.enforce_capacity()

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "capacity": self.capacity,
            "decoherence_probability": self.decoherence_probability,
            "occupancy": self.occupancy(),
            "count": len(self._contents),
            "state_ids": [state.id for state in self._contents],
        }


class QPUCommunicationMemory(FiniteMemory):
    """Compatibility finite memory used by the old QPU receive-buffer API."""
