"""Central simulator orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .computation import FixedPeriodicComputation
from .exceptions import ConfigurationError
from .factory import BernoulliMagicStateFactory, MagicStateFactory
from .memory import FiniteMemory
from .network import LossyNetwork, NetworkEdge
from .policies import DropNewestOnOverflow, RoundRobinRoutingPolicy, RoutingPolicy, StoragePolicy
from .qpu import QPU
from .stats import SimulationStats
from .tokens import validate_positive_int


class Simulator:
    """Central discrete-time coordinator for factories, memories, network, QPUs, and computation."""

    def __init__(
        self,
        factories: dict[str, object],
        memories: dict[str, FiniteMemory],
        network: LossyNetwork,
        qpus: dict[str, QPU],
        computation,
        factory_memory_map: dict[str, str] | None = None,
        qpu_memory_map: dict[str, str] | None = None,
        seed: int | None = None,
        stats: SimulationStats | None = None,
    ) -> None:
        self.factories = factories
        self.memories = memories
        self.network = network
        self.qpus = qpus
        self.computation = computation
        self.factory_memory_map = factory_memory_map or {}
        self.qpu_memory_map = qpu_memory_map or {}
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.stats = stats or SimulationStats()
        self.t = 0
        self._last_requests = []
        self.validate()

    def validate(self) -> None:
        """Check that all factories, memories, QPUs, and network edges connect."""
        # Validate wiring early so a missing route fails before a run has partly
        # advanced. The simulator relies on static maps for the first version.
        for factory_id, factory in self.factories.items():
            memory_id = self.factory_memory_map.get(factory_id, getattr(factory, "attached_memory_id", None))
            if memory_id is None:
                raise ConfigurationError(f"factory {factory_id} has no attached memory")
            if memory_id not in self.memories:
                raise ConfigurationError(f"factory {factory_id} references unknown memory {memory_id}")
        for qpu_id in self.qpus:
            memory_id = self.qpu_memory_map.get(qpu_id)
            if memory_id is None:
                raise ConfigurationError(f"qpu {qpu_id} has no source memory route")
            if memory_id not in self.memories:
                raise ConfigurationError(f"qpu {qpu_id} references unknown memory {memory_id}")
            self.network.get_edge(memory_id, qpu_id)
        qpu_id = getattr(self.computation, "qpu_id", None)
        if qpu_id is not None and qpu_id not in self.qpus:
            raise ConfigurationError(f"computation references unknown qpu {qpu_id}")

    def route_request_to_memory(self, request) -> str:
        """Resolve a computation request to its source memory using static routing."""
        try:
            return self.qpu_memory_map[request.qpu_id]
        except KeyError as exc:
            raise ConfigurationError(f"no memory route for qpu {request.qpu_id}") from exc

    def step(self) -> SimulationStats:
        """Advance the whole system by exactly one discrete time step."""
        t = self.t
        # Age/decohere stored resources before new work is created at this
        # time step. Produced states are still allowed to be used at the same t.
        for memory in self.memories.values():
            memory.step(t, self.rng)
        for qpu in self.qpus.values():
            qpu.step(t, self.rng)

        # First computation step opens new rounds/nodes and exposes demand.
        self.computation.step(t, self.rng)

        # Factories only produce states. The simulator is responsible for
        # inserting those states into the attached memories.
        for factory_id, factory in self.factories.items():
            states = list(factory.step(t, self.rng))
            memory_id = self.factory_memory_map.get(factory_id, getattr(factory, "attached_memory_id", None))
            memory = self.memories[memory_id]
            accepted = memory.add_many(states, t=t, rng=self.rng)
            self.stats.inc("states_created", len(states))
            self.stats.inc("states_accepted_by_memory", len(accepted))
            self.stats.inc("states_rejected_by_memory", len(states) - len(accepted))

        requests = self.computation.get_active_requests(t)
        self._last_requests = requests
        delivered_by_qpu = {qpu_id: 0 for qpu_id in self.qpus}

        for request in requests:
            qpu = self.qpus[request.qpu_id]
            memory_id = self.route_request_to_memory(request)
            memory = self.memories[memory_id]
            needed = request.n_states

            # Establish only the Bell pairs missing for this request. Extra
            # Bell pairs already stored at the QPU can be reused.
            available_bp = qpu.available_bell_pairs(source_id=memory.id)
            missing_bp = max(0, needed - available_bp)
            self.stats.inc("bell_pairs_attempted", missing_bp)
            created = self.network.establish_bell_pairs(
                source_id=memory.id,
                qpu=qpu,
                n=missing_bp,
                t=t,
                rng=self.rng,
            )
            self.stats.inc("bell_pairs_created", len(created))

            # Network.teleport is defensive and will only consume resources that
            # exist. We compute `possible` for counters before the call mutates
            # memory and QPU Bell-pair state.
            possible = min(needed, len(memory.list()), qpu.available_bell_pairs(source_id=memory.id))
            before_lost = self.network.lost
            before_in_flight = len(self.network.in_flight)
            delivered_states = self.network.teleport(
                memory=memory,
                qpu=qpu,
                n=needed,
                t=t,
                rng=self.rng,
            )
            new_in_flight = len(self.network.in_flight) - before_in_flight
            failures = self.network.lost - before_lost
            self.stats.inc("teleport_attempts", possible)
            self.stats.inc("teleport_successes", len(delivered_states) + max(0, new_in_flight))
            self.stats.inc("teleport_failures", failures)
            for state in delivered_states:
                qpu.receive_magic_state(state, t=t)
            delivered_by_qpu[qpu.id] += len(delivered_states)

        # Positive-latency teleportation queues states in the network. The
        # simulator releases any arrivals and then reports them to computation.
        for qpu_id, state in self.network.step(t, self.rng):
            self.qpus[qpu_id].receive_magic_state(state, t=t)
            delivered_by_qpu[qpu_id] += 1

        for qpu_id, n in delivered_by_qpu.items():
            if n > 0:
                self.computation.receive_magic_states(qpu_id, n, t)
                self.stats.inc("states_delivered", n)
                consumed = min(n, getattr(self.computation, "total_magic_states_consumed", n))
                self.stats.counters["states_consumed"] = getattr(
                    self.computation, "total_magic_states_consumed", consumed
                )

        # A second computation step lets work complete in the same time step as
        # delivery. Computation classes should make repeated calls at the same t
        # idempotent for stall accounting.
        self.computation.step(t, self.rng)
        if hasattr(self.computation, "completed_work_count"):
            self.stats.counters["completed_operations"] = self.computation.completed_work_count()
        if getattr(self.computation, "failed", False):
            self.stats.counters["failed_operations"] = 1
        self.stats.record_step(t, self, delivered_by_qpu=delivered_by_qpu)
        self.t += 1
        return self.stats

    def run(self, num_steps: int | None = None, *, duration: int | None = None) -> SimulationStats:
        """Run several time steps and return the shared statistics object."""
        steps = num_steps if num_steps is not None else duration
        validate_positive_int(steps, "num_steps")
        for _ in range(steps):
            self.step()
        return self.stats

    def reset(self, seed: int | None = None) -> None:
        """Reset simulator time, RNG, and statistics without rebuilding components."""
        self.seed = self.seed if seed is None else seed
        self.rng = np.random.default_rng(self.seed)
        self.t = 0
        self.stats = SimulationStats()

    def snapshot(self) -> dict:
        """Return a nested serializable view of the full simulation state."""
        return {
            "t": self.t,
            "factories": {fid: factory.snapshot() for fid, factory in self.factories.items()},
            "memories": {mid: memory.snapshot() for mid, memory in self.memories.items()},
            "network": self.network.snapshot(),
            "qpus": {qid: qpu.snapshot() for qid, qpu in self.qpus.items()},
            "computation": self.computation.snapshot(),
            "stats": self.stats.as_dict(),
        }

    def update_component_params(self, component_type: str, component_id: str, **kwargs) -> None:
        """Strictly update one component or network edge during a run."""
        collections = {
            "factory": self.factories,
            "memory": self.memories,
            "qpu": self.qpus,
        }
        if component_type == "network_edge":
            source_id, target_id = component_id.split("->", 1)
            self.network.update_edge_params(source_id, target_id, **kwargs)
            return
        if component_type == "computation":
            self.computation.update_params(**kwargs)
            return
        if component_type not in collections:
            raise ValueError(f"unknown component_type {component_type}")
        collections[component_type][component_id].update_params(**kwargs)


@dataclass
class MagicStateSimulator:
    """Compatibility adapter for the original one-source-memory simulator API."""

    factory: MagicStateFactory
    source_memory: FiniteMemory
    qpus: list[QPU]
    network: LossyNetwork = field(default_factory=LossyNetwork)
    storage_policy: StoragePolicy = field(default_factory=DropNewestOnOverflow)
    routing_policy: RoutingPolicy = field(default_factory=RoundRobinRoutingPolicy)
    computation: object | None = None
    stats: SimulationStats = field(default_factory=SimulationStats)

    def __post_init__(self) -> None:
        """Build a planned Simulator behind the old one-memory compatibility API."""
        if not self.qpus:
            raise ConfigurationError("at least one QPU is required")
        primary_qpu = self.qpus[0]

        # Old examples constructed `FiniteMemory(8)` with the default ID. Give
        # that memory a stable route ID before building the planned Simulator.
        if not self.source_memory.id:
            self.source_memory.id = "memory_0"
        if self.source_memory.id == "memory":
            self.source_memory.id = "memory_0"
        for qpu in self.qpus:
            if (self.source_memory.id, qpu.id) not in self.network.edges:
                self.network.add_edge(
                    NetworkEdge(
                        source_id=self.source_memory.id,
                        target_id=qpu.id,
                        bell_pair_success_probability=1.0 - self.network.loss_probability,
                        teleport_success_probability=1.0,
                        latency=self.network.latency,
                    )
                )
        if self.computation is None:
            self.computation = FixedPeriodicComputation(qpu_id=primary_qpu.id)
        elif isinstance(self.computation, FixedPeriodicComputation):
            self.computation.qpu_id = primary_qpu.id
        self._sim = Simulator(
            factories={"factory_0": self.factory},
            memories={self.source_memory.id: self.source_memory},
            network=self.network,
            qpus={qpu.id: qpu for qpu in self.qpus},
            computation=self.computation,
            factory_memory_map={"factory_0": self.source_memory.id},
            qpu_memory_map={qpu.id: self.source_memory.id for qpu in self.qpus},
            stats=self.stats,
        )

    def step(self, time: int | None = None) -> SimulationStats:
        """Compatibility wrapper for advancing one step."""
        return self._sim.step()

    def run(self, duration: int) -> SimulationStats:
        """Compatibility wrapper for running several steps."""
        return self._sim.run(duration)
