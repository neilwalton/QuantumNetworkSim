"""Simulator orchestration."""
from __future__ import annotations
from dataclasses import dataclass, field
from .factory import MagicStateFactory
from .memory import FiniteMemory
from .network import LossyNetwork
from .policies import DropNewestOnOverflow, RoundRobinRoutingPolicy, StoragePolicy, RoutingPolicy
from .qpu import QPU
from .stats import SimulationStats
from .tokens import validate_positive_int

@dataclass
class MagicStateSimulator:
    factory: MagicStateFactory
    source_memory: FiniteMemory
    qpus: list[QPU]
    network: LossyNetwork = field(default_factory=LossyNetwork)
    storage_policy: StoragePolicy = field(default_factory=DropNewestOnOverflow)
    routing_policy: RoutingPolicy = field(default_factory=RoundRobinRoutingPolicy)
    computation: object | None = None
    stats: SimulationStats = field(default_factory=SimulationStats)

    def step(self, time:int) -> SimulationStats:
        self.network.tick(time)
        produced = self.factory.produce(time); self.stats.produced += len(produced)
        admitted = self.storage_policy.admit(produced, self.source_memory, time)
        self.source_memory.add(admitted); self.stats.admitted += len(admitted)
        while self.source_memory.available and self.qpus:
            token = self.source_memory.take(1)[0]
            destination = self.routing_policy.select_destination(self.qpus, token, time)
            if destination is None: break
            if self.network.send(token, destination, time): self.stats.sent += 1
        self.network.tick(time)
        self.stats.delivered = self.network.delivered; self.stats.lost = self.network.lost
        if self.computation is not None and self.qpus:
            demand = self.computation.demand_at(time)
            if demand:
                try:
                    self.qpus[0].execute(demand); self.stats.completed_operations += 1; self.stats.consumed += demand
                    ready = getattr(self.computation, "ready_nodes", lambda: ())()
                    if ready and hasattr(self.computation, "mark_completed"): self.computation.mark_completed(ready[0])
                except Exception:
                    self.stats.failed_operations += 1
        return self.stats

    def run(self, duration:int) -> SimulationStats:
        validate_positive_int(duration,"duration")
        for time in range(duration): self.step(time)
        return self.stats
