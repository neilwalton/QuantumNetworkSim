"""Lossy Bell-pair and teleportation network."""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

from .exceptions import ConfigurationError, MemoryFullError
from .qpu import QPU
from .tokens import BellPair, IdGenerator, MagicState, validate_non_negative_int, validate_positive_number, validate_probability


@dataclass
class NetworkEdge:
    source_id: str
    target_id: str
    loss_probability: float | None = None
    bell_pair_success_probability: float | None = None
    teleport_success_probability: float = 1.0
    latency: int = 0
    communication_capacity: int | float = float("inf")
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        if not self.target_id:
            raise ValueError("target_id must be non-empty")
        if self.loss_probability is not None:
            loss_probability = validate_probability(self.loss_probability, "loss_probability")
            if self.bell_pair_success_probability is None:
                self.bell_pair_success_probability = 1.0 - loss_probability
            else:
                expected = 1.0 - loss_probability
                if abs(float(self.bell_pair_success_probability) - expected) > 1e-12:
                    raise ValueError("loss_probability conflicts with bell_pair_success_probability")
        if self.bell_pair_success_probability is None:
            self.bell_pair_success_probability = 1.0
        self.bell_pair_success_probability = validate_probability(
            self.bell_pair_success_probability, "bell_pair_success_probability"
        )
        self.teleport_success_probability = validate_probability(
            self.teleport_success_probability, "teleport_success_probability"
        )
        validate_non_negative_int(self.latency, "latency")
        self.communication_capacity = validate_positive_number(
            self.communication_capacity, "communication_capacity", allow_infinity=True
        )


@dataclass
class InFlightDelivery:
    state: MagicState
    target_qpu_id: str
    delivery_time: int


@dataclass
class LossyNetwork:
    """Network graph for Bell-pair establishment and magic-state teleportation."""

    loss_probability: float = 0.0
    latency: int = 0
    seed: int | None = None
    _compat_in_flight: list[tuple[int, object, MagicState]] = field(default_factory=list, init=False, repr=False)
    in_flight: list[InFlightDelivery] = field(default_factory=list, init=False, repr=False)
    edges: dict[tuple[str, str], NetworkEdge] = field(default_factory=dict, init=False, repr=False)
    delivered: int = 0
    lost: int = 0

    def __post_init__(self) -> None:
        self.loss_probability = validate_probability(self.loss_probability, "loss_probability")
        validate_non_negative_int(self.latency, "latency")
        self._rng = random.Random(self.seed)
        self.bell_pair_ids = IdGenerator("bell_pair")

    def add_edge(self, edge: NetworkEdge) -> None:
        self.edges[(edge.source_id, edge.target_id)] = edge

    def get_edge(self, source_id: str, target_id: str) -> NetworkEdge:
        try:
            return self.edges[(source_id, target_id)]
        except KeyError as exc:
            raise ConfigurationError(f"no network edge from {source_id} to {target_id}") from exc

    def update_edge_params(self, source_id: str, target_id: str, **kwargs) -> None:
        edge = self.get_edge(source_id, target_id)
        values = edge.__dict__.copy()
        for key, value in kwargs.items():
            if key not in values:
                raise AttributeError(f"NetworkEdge has no parameter {key}")
            values[key] = value
        self.edges[(source_id, target_id)] = NetworkEdge(**values)

    def establish_bell_pairs(self, source_id: str, qpu: QPU, n: int, t: int, rng) -> list[BellPair]:
        edge = self.get_edge(source_id, qpu.id)
        created: list[BellPair] = []
        for _ in range(max(0, n)):
            if rng.random() < edge.bell_pair_success_probability:
                bell_pair = BellPair(
                    id=self.bell_pair_ids.new(),
                    source_id=source_id,
                    target_qpu_id=qpu.id,
                    created_at=t,
                    fidelity=edge.metadata.get("bell_pair_fidelity"),
                )
                if qpu.add_bell_pair(bell_pair, t=t, rng=rng):
                    created.append(bell_pair)
        return created

    def teleport(self, memory, qpu: QPU, n: int, t: int, rng) -> list[MagicState]:
        edge = self.get_edge(memory.id, qpu.id)
        delivered: list[MagicState] = []
        attempts = max(0, n)
        for _ in range(attempts):
            if not memory.list() or qpu.available_bell_pairs(source_id=memory.id) <= 0:
                break
            state = memory.pop_available(1, t=t)[0]
            bell_pair = qpu.consume_bell_pair(source_id=memory.id)
            if bell_pair is None:
                memory.add(state, t=t, rng=rng)
                break
            state.mark("teleport_attempted")
            if rng.random() < edge.teleport_success_probability:
                if edge.latency == 0:
                    state.mark("delivered")
                    delivered.append(state)
                else:
                    self.in_flight.append(
                        InFlightDelivery(
                            state=state,
                            target_qpu_id=qpu.id,
                            delivery_time=t + edge.latency,
                        )
                    )
            else:
                state.mark("teleport_failed")
                state.mark("destroyed")
                self.lost += 1
        self.delivered += len(delivered)
        return delivered

    def step(self, t: int, rng=None) -> list[tuple[str, MagicState]]:
        ready: list[tuple[str, MagicState]] = []
        pending: list[InFlightDelivery] = []
        for delivery in self.in_flight:
            if delivery.delivery_time <= t:
                delivery.state.mark("delivered")
                ready.append((delivery.target_qpu_id, delivery.state))
            else:
                pending.append(delivery)
        self.in_flight = pending
        self.delivered += len(ready)
        return ready

    def send(self, token: MagicState, destination, time: int) -> bool:
        """Compatibility direct token send used by the original simulator API."""
        if self._rng.random() < self.loss_probability:
            self.lost += 1
            token.mark("lost")
            return False
        self._compat_in_flight.append((time + self.latency, destination, token))
        return True

    def tick(self, time: int):
        """Compatibility delivery tick for direct sends."""
        ready = []
        pending = []
        for item in self._compat_in_flight:
            arrival, dest, token = item
            if arrival <= time:
                ready.append(item)
            else:
                pending.append(item)
        self._compat_in_flight = pending
        delivered_tokens = []
        for _, dest, token in ready:
            try:
                dest.receive((token,))
            except MemoryFullError:
                self.lost += 1
                token.mark("lost")
            else:
                self.delivered += 1
                delivered_tokens.append(token)
        return tuple(delivered_tokens)

    def update_params(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.__post_init__()

    def snapshot(self) -> dict:
        return {
            "edges": {f"{src}->{dst}": edge.__dict__.copy() for (src, dst), edge in self.edges.items()},
            "in_flight": len(self.in_flight),
            "delivered": self.delivered,
            "lost": self.lost,
        }
