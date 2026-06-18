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
        # Support both the planned constructor shape (`FiniteMemory("m", 50)`)
        # and the original compatibility shape (`FiniteMemory(50)`).
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
        """Install default policies and validate the memory configuration."""
        self.drop_policy = self.drop_policy or DefaultDropPolicy()
        self.selection_policy = self.selection_policy or OldestFirstSelectionPolicy()
        self.validate()

    def validate(self) -> None:
        """Validate memory ID, capacity, and decoherence probability."""
        if not self.id:
            raise ValueError("id must be non-empty")
        self.capacity = validate_positive_number(self.capacity, "capacity", allow_infinity=True)
        self.decoherence_probability = validate_probability(
            self.decoherence_probability, "decoherence_probability"
        )

    def __len__(self) -> int:
        """Return the number of stored states, not total occupancy."""
        return len(self._contents)

    @property
    def available(self) -> int:
        """Return how many state objects are currently stored."""
        return len(self._contents)

    @property
    def remaining_capacity(self) -> int | float:
        """Return unused occupancy capacity."""
        return self.capacity - self.occupancy()

    def list(self) -> list[MagicState]:
        """Return a shallow copy of stored states so callers cannot mutate the list."""
        return list(self._contents)

    def peek(self) -> tuple[MagicState, ...]:
        """Compatibility read-only view of stored states."""
        return tuple(self._contents)

    def clear(self) -> None:
        """Remove all stored states without marking lifecycle flags."""
        self._contents.clear()

    def occupancy(self) -> int | float:
        """Return total occupancy used by all stored states."""
        return sum(state.occupancy for state in self._contents)

    def add(self, state, t: int = 0, rng=None) -> bool | int:
        """Add either one state using planned behavior or a batch using compatibility behavior."""
        # A list/tuple input means the old FIFO API is being used. Keep that
        # path strict so old code still receives MemoryFullError on overflow.
        if isinstance(state, (list, tuple)):
            return self._add_compat_many(state, t=t, rng=rng)
        return self._add_one(state, t=t, rng=rng)

    def _add_compat_many(self, states, t: int, rng) -> int:
        """Original strict batch insertion path used by old examples/tests."""
        states = tuple(states)
        if sum(state.occupancy for state in states) > self.remaining_capacity:
            raise MemoryFullError("memory capacity exceeded")
        for state in states:
            self._contents.append(state)
            state.mark("in_memory")
        return len(states)

    def _add_one(self, state: MagicState, t: int, rng=None) -> bool:
        """Insert one state, dropping old contents if needed to respect capacity."""
        if state.occupancy > self.capacity:
            state.mark("rejected_too_large")
            return False

        # Planned behavior: make room by dropping existing contents according
        # to the configured policy. If no drop candidate exists, reject the new
        # state rather than exceeding capacity.
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
        """Insert several states independently and return the accepted subset."""
        accepted: list[MagicState] = []
        for state in states:
            if self._add_one(state, t=t, rng=rng):
                accepted.append(state)
        return accepted

    def pop_by_id(self, state_id: str) -> MagicState | None:
        """Remove and return the state with the requested ID, if present."""
        for state in list(self._contents):
            if state.id == state_id:
                self._contents.remove(state)
                state.flags.discard("in_memory")
                return state
        return None

    def pop_available(self, n: int, t: int = 0, policy: MagicStateSelectionPolicy | None = None) -> list[MagicState]:
        """Remove up to ``n`` states according to the selection policy."""
        if n <= 0:
            return []
        # Selection policy decides which states leave memory; this keeps memory
        # storage independent from future scheduling heuristics.
        selected = (policy or self.selection_policy).select(self._contents, n, t=t, rng=None)
        popped: list[MagicState] = []
        for state in selected:
            if state in self._contents:
                self._contents.remove(state)
                state.flags.discard("in_memory")
                popped.append(state)
        return popped

    def take(self, count: int = 1) -> tuple[MagicState, ...]:
        """Compatibility FIFO-style removal that raises if not enough states exist."""
        if len(self._contents) < count:
            raise InsufficientTokensError("not enough tokens in memory")
        return tuple(self.pop_available(count))

    def discard_oldest(self, count: int = 1) -> tuple[MagicState, ...]:
        """Remove up to ``count`` oldest states and mark them as dropped."""
        removed = tuple(self.pop_available(count))
        for state in removed:
            state.mark("dropped")
        return removed

    def step(self, t: int, rng) -> None:
        """Apply per-step memory effects: binary decoherence and capacity enforcement."""
        survivors: list[MagicState] = []
        for state in self._contents:
            # Version one uses binary decoherence: a decohered state is removed.
            # Later models can replace this with continuous fidelity decay.
            if rng.random() < self.decoherence_probability:
                state.mark("decohered")
            else:
                survivors.append(state)
        self._contents = survivors
        self.enforce_capacity(t=t, rng=rng)

    def enforce_capacity(self, t: int = 0, rng=None) -> None:
        """Drop stored states until total occupancy is within capacity."""
        # Called after capacity changes as well as during step(). This guarantees
        # snapshots never report occupancy above the configured capacity.
        while self.occupancy() > self.capacity and self._contents:
            victim = self.drop_policy.select(self._contents, t=t, rng=rng)
            if victim is None:
                break
            self._contents.remove(victim)
            victim.mark("dropped")

    def update_params(self, **kwargs) -> None:
        """Strictly update memory parameters and enforce any new capacity."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.validate()
        self.enforce_capacity()

    def snapshot(self) -> dict:
        """Return a serializable summary of current memory state."""
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
