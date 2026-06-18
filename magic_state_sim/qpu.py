"""QPU model with Bell-pair communication memory."""
from __future__ import annotations

from .exceptions import InsufficientTokensError
from .memory import QPUCommunicationMemory
from .policies import DefaultDropPolicy, DropPolicy
from .tokens import BellPair, MagicState, validate_positive_int, validate_positive_number, validate_probability


class QPU:
    """A QPU that stores Bell pairs and can receive magic states."""

    def __init__(
        self,
        id: str | None = None,
        memory: QPUCommunicationMemory | None = None,
        *,
        name: str | None = None,
        bell_pair_capacity: int | float = float("inf"),
        bell_pair_decoherence_probability: float = 0.0,
        bell_pair_drop_policy: DropPolicy | None = None,
    ) -> None:
        self.id = id or name
        if not self.id:
            raise ValueError("id must be non-empty")
        self.name = self.id
        self.memory = memory or QPUCommunicationMemory(capacity=16, id=f"{self.id}_compat_memory")
        self.bell_pair_capacity = bell_pair_capacity
        self.bell_pair_decoherence_probability = bell_pair_decoherence_probability
        self.bell_pair_drop_policy = bell_pair_drop_policy or DefaultDropPolicy()
        self.bell_pairs: list[BellPair] = []
        self.received_magic_states: list[MagicState] = []
        self.consumed_tokens = 0
        self.failed_operations = 0
        self.completed_operations = 0
        self.validate()

    def validate(self) -> None:
        """Validate Bell-pair capacity and decoherence settings."""
        self.bell_pair_capacity = validate_positive_number(
            self.bell_pair_capacity, "bell_pair_capacity", allow_infinity=True
        )
        self.bell_pair_decoherence_probability = validate_probability(
            self.bell_pair_decoherence_probability, "bell_pair_decoherence_probability"
        )

    def bell_pair_occupancy(self, source_id: str | None = None) -> int | float:
        """Return total Bell-pair occupancy, optionally for one source memory."""
        return sum(bp.occupancy for bp in self._matching_bell_pairs(source_id))

    def _matching_bell_pairs(self, source_id: str | None = None) -> list[BellPair]:
        """Return stored Bell pairs filtered by source if requested."""
        if source_id is None:
            return list(self.bell_pairs)
        return [bp for bp in self.bell_pairs if bp.source_id == source_id]

    def add_bell_pair(self, bell_pair: BellPair, t: int = 0, rng=None) -> bool:
        """Store one Bell pair, dropping existing pairs if needed for capacity."""
        if bell_pair.occupancy > self.bell_pair_capacity:
            bell_pair.mark("rejected_too_large")
            return False

        # Bell-pair capacity is measured by occupancy, matching magic-state
        # memory. Drop policies make capacity shrink and overflow deterministic.
        while self.bell_pair_occupancy() + bell_pair.occupancy > self.bell_pair_capacity:
            victim = self.bell_pair_drop_policy.select(self.bell_pairs, t=t, rng=rng)
            if victim is None:
                bell_pair.mark("rejected_no_drop_candidate")
                return False
            self.bell_pairs.remove(victim)
            victim.mark("dropped")
        self.bell_pairs.append(bell_pair)
        bell_pair.mark("in_qpu_memory")
        return True

    def consume_bell_pair(self, source_id: str | None = None) -> BellPair | None:
        """Remove and return the oldest Bell pair matching the requested source."""
        matches = self._matching_bell_pairs(source_id)
        if not matches:
            return None

        # Consume oldest first for predictable behavior. More advanced routing
        # can later replace this with a fidelity-aware policy.
        bell_pair = min(matches, key=lambda bp: bp.created_at)
        self.bell_pairs.remove(bell_pair)
        bell_pair.flags.discard("in_qpu_memory")
        bell_pair.mark("consumed")
        return bell_pair

    def available_bell_pairs(self, source_id: str | None = None) -> int:
        """Count stored Bell pairs, optionally filtered by source."""
        return len(self._matching_bell_pairs(source_id))

    def receive_magic_state(self, state: MagicState, t: int = 0) -> None:
        """Record that a magic state arrived successfully at this QPU."""
        state.mark("delivered")
        self.received_magic_states.append(state)

    def drain_received_magic_states(self) -> int:
        """Clear delivered-state records and return how many were present."""
        count = len(self.received_magic_states)
        self.received_magic_states.clear()
        return count

    def receive(self, tokens) -> int:
        """Compatibility method: add magic states to the old receive buffer."""
        # Compatibility path for the original API where the QPU had a magic-state
        # receive buffer. Planned simulations should use receive_magic_state().
        tokens = tuple(tokens)
        added = self.memory.add(tokens)
        for token in tokens:
            if isinstance(token, MagicState):
                self.received_magic_states.append(token)
        return int(added)

    def can_execute(self, tokens_required: int = 1) -> bool:
        """Compatibility method: check if enough buffered magic states exist."""
        validate_positive_int(tokens_required, "tokens_required")
        return self.memory.available >= tokens_required or len(self.received_magic_states) >= tokens_required

    def execute(self, tokens_required: int = 1):
        """Compatibility method: consume buffered magic states for an operation."""
        if not self.can_execute(tokens_required):
            self.failed_operations += 1
            raise InsufficientTokensError("QPU lacks required magic-state tokens")
        if self.memory.available >= tokens_required:
            tokens = self.memory.take(tokens_required)
            for token in tokens:
                token.mark("consumed")
                # Tokens received through the compatibility path are also kept
                # in the planned arrival log; remove them so they cannot be
                # consumed twice.
                if token in self.received_magic_states:
                    self.received_magic_states.remove(token)
        else:
            tokens = tuple(self.received_magic_states[:tokens_required])
            del self.received_magic_states[:tokens_required]
            for token in tokens:
                token.mark("consumed")
        self.consumed_tokens += len(tokens)
        self.completed_operations += 1
        return tokens

    def step(self, t: int, rng) -> None:
        """Apply Bell-pair decoherence and capacity enforcement for one step."""
        survivors: list[BellPair] = []
        for bell_pair in self.bell_pairs:
            # Version one uses binary Bell-pair decoherence: decohered pairs are
            # removed from communication memory.
            if rng.random() < self.bell_pair_decoherence_probability:
                bell_pair.mark("decohered")
            else:
                survivors.append(bell_pair)
        self.bell_pairs = survivors
        self.enforce_capacity(t=t, rng=rng)

    def enforce_capacity(self, t: int = 0, rng=None) -> None:
        """Drop Bell pairs until communication-memory occupancy is within capacity."""
        while self.bell_pair_occupancy() > self.bell_pair_capacity and self.bell_pairs:
            victim = self.bell_pair_drop_policy.select(self.bell_pairs, t=t, rng=rng)
            if victim is None:
                break
            self.bell_pairs.remove(victim)
            victim.mark("dropped")

    def update_params(self, **kwargs) -> None:
        """Strictly update QPU parameters and enforce any new capacity."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.validate()
        self.enforce_capacity()

    def snapshot(self) -> dict:
        """Return a serializable summary of QPU resources and counters."""
        return {
            "id": self.id,
            "bell_pair_capacity": self.bell_pair_capacity,
            "bell_pair_count": len(self.bell_pairs),
            "bell_pair_occupancy": self.bell_pair_occupancy(),
            "received_magic_states": len(self.received_magic_states),
            "consumed_tokens": self.consumed_tokens,
            "failed_operations": self.failed_operations,
            "completed_operations": self.completed_operations,
        }
