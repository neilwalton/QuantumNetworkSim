"""Computation demand models."""
from __future__ import annotations
from dataclasses import dataclass, field
from .tokens import validate_positive_int, validate_non_negative_int

@dataclass
class FixedPeriodicComputation:
    period: int = 1
    tokens_per_operation: int = 1
    start_time: int = 0
    def __post_init__(self): validate_positive_int(self.period,"period"); validate_positive_int(self.tokens_per_operation,"tokens_per_operation"); validate_non_negative_int(self.start_time,"start_time")
    def demand_at(self, time:int) -> int:
        return self.tokens_per_operation if time >= self.start_time and (time-self.start_time) % self.period == 0 else 0

@dataclass
class DAGComputation:
    nodes: dict[str, int]
    edges: dict[str, tuple[str, ...]] = field(default_factory=dict)
    completed: set[str] = field(default_factory=set, init=False)
    def ready_nodes(self):
        return tuple(n for n in self.nodes if n not in self.completed and all(dep in self.completed for dep in self.edges.get(n, ())))
    def demand_at(self, time:int) -> int:
        ready=self.ready_nodes(); return self.nodes[ready[0]] if ready else 0
    def mark_completed(self, node:str): self.completed.add(node)
