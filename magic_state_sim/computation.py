"""Computation demand models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .exceptions import ValidationError
from .tokens import IdGenerator, validate_non_negative_int, validate_positive_int


@dataclass
class MagicStateRequest:
    qpu_id: str
    n_states: int
    request_id: str
    priority: int = 0
    deadline: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.qpu_id:
            raise ValidationError("qpu_id must be non-empty")
        validate_non_negative_int(self.n_states, "n_states")
        if not self.request_id:
            raise ValidationError("request_id must be non-empty")


class FixedPeriodicComputation:
    """One active periodic computation round at a time."""

    def __init__(
        self,
        qpu_id: str = "qpu_0",
        interval: int | None = None,
        magic_states_per_round: int | None = None,
        *,
        period: int | None = None,
        tokens_per_operation: int | None = None,
        start_time: int = 0,
        allow_failure: bool = False,
        failure_after_stall: int | None = None,
    ) -> None:
        self.qpu_id = qpu_id
        self.interval = interval if interval is not None else (period if period is not None else 1)
        self.magic_states_per_round = (
            magic_states_per_round
            if magic_states_per_round is not None
            else (tokens_per_operation if tokens_per_operation is not None else 1)
        )
        self.start_time = start_time
        self.allow_failure = allow_failure
        self.failure_after_stall = failure_after_stall
        self.completed_rounds = 0
        self.active_round_id: str | None = None
        self.next_round_time = start_time
        self.remaining_magic_states = 0
        self.stall_time = 0
        self.failed = False
        self.total_magic_states_consumed = 0
        self.wasted_magic_states = 0
        self._ids = IdGenerator("round")
        self._last_stall_t: int | None = None
        self.validate()

    @property
    def period(self) -> int:
        return self.interval

    @property
    def tokens_per_operation(self) -> int:
        return self.magic_states_per_round

    def validate(self) -> None:
        """Validate timing, demand, and optional failure parameters."""
        if not self.qpu_id:
            raise ValidationError("qpu_id must be non-empty")
        validate_positive_int(self.interval, "interval")
        validate_positive_int(self.magic_states_per_round, "magic_states_per_round")
        validate_non_negative_int(self.start_time, "start_time")
        if self.failure_after_stall is not None:
            validate_positive_int(self.failure_after_stall, "failure_after_stall")

    def demand_at(self, time: int) -> int:
        """Compatibility helper returning periodic demand at a specific time."""
        if time < self.start_time:
            return 0
        return self.magic_states_per_round if (time - self.start_time) % self.interval == 0 else 0

    def step(self, t: int, rng=None) -> None:
        """Open due rounds, count stall time, and complete satisfied rounds."""
        if self.failed:
            return

        # Open a new round as soon as it is due. The simulator may call step()
        # again later at the same t after deliveries arrive.
        if self.active_round_id is None and t >= self.next_round_time:
            self.active_round_id = self._ids.new()
            self.remaining_magic_states = self.magic_states_per_round
        if self.active_round_id is None:
            return
        if self.remaining_magic_states <= 0:
            # Completing after delivery in the same time step avoids adding an
            # artificial one-step delay to every successful teleportation.
            self.completed_rounds += 1
            self.active_round_id = None
            self.next_round_time = t + self.interval
            self._last_stall_t = None
            return
        if self._last_stall_t != t:
            # The simulator can call step twice at the same t. Count at most one
            # stall tick per simulation time step.
            self.stall_time += 1
            self._last_stall_t = t
        if (
            self.allow_failure
            and self.failure_after_stall is not None
            and self.stall_time >= self.failure_after_stall
        ):
            self.failed = True

    def get_active_requests(self, t: int) -> list[MagicStateRequest]:
        """Return the current unmet magic-state request, if a round is active."""
        if self.failed or self.active_round_id is None or self.remaining_magic_states <= 0:
            return []
        return [
            MagicStateRequest(
                qpu_id=self.qpu_id,
                n_states=self.remaining_magic_states,
                request_id=self.active_round_id,
            )
        ]

    def receive_magic_states(self, qpu_id: str, n: int, t: int) -> None:
        """Apply delivered magic states to the active round's remaining demand."""
        validate_non_negative_int(n, "n")
        if qpu_id != self.qpu_id or n == 0:
            self.wasted_magic_states += n
            return
        if self.active_round_id is None:
            # This should be uncommon because the simulator serves active
            # requests only, but it keeps accounting robust for external callers.
            self.wasted_magic_states += n
            return
        consumed = min(n, self.remaining_magic_states)
        self.remaining_magic_states -= consumed
        self.total_magic_states_consumed += consumed
        self.wasted_magic_states += n - consumed

    def is_complete(self) -> bool:
        """Periodic workloads do not have a natural terminal complete state."""
        return False

    def completed_work_count(self) -> int:
        """Return how many periodic rounds have completed."""
        return self.completed_rounds

    def throughput(self, t: int) -> float:
        """Return completed rounds per elapsed simulation step."""
        return self.completed_rounds / max(1, t + 1)

    def update_params(self, **kwargs) -> None:
        """Strictly update periodic workload parameters."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.validate()

    def snapshot(self) -> dict:
        """Return a serializable summary of periodic workload state."""
        return {
            "qpu_id": self.qpu_id,
            "interval": self.interval,
            "magic_states_per_round": self.magic_states_per_round,
            "completed_rounds": self.completed_rounds,
            "active_round_id": self.active_round_id,
            "remaining_magic_states": self.remaining_magic_states,
            "stall_time": self.stall_time,
            "failed": self.failed,
        }


@dataclass
class ComputationNode:
    id: str
    qpu_id: str
    compute_time: int
    magic_states_required: int
    dependencies: list[str] = field(default_factory=list)
    status: str = "blocked"
    start_time: int | None = None
    finish_time: int | None = None
    remaining_compute_time: int | None = None
    remaining_magic_states: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("node id must be non-empty")
        if not self.qpu_id:
            raise ValidationError("qpu_id must be non-empty")
        validate_non_negative_int(self.compute_time, "compute_time")
        validate_non_negative_int(self.magic_states_required, "magic_states_required")
        if self.remaining_compute_time is None:
            self.remaining_compute_time = self.compute_time
        if self.remaining_magic_states is None:
            self.remaining_magic_states = self.magic_states_required


class DAGComputation:
    """Basic DAG computation with one running node per QPU."""

    def __init__(
        self,
        nodes: dict[str, int | ComputationNode],
        edges: dict[str, tuple[str, ...] | list[str]] | None = None,
    ) -> None:
        self.nodes: dict[str, ComputationNode] = {}
        self.edges = {node_id: tuple(deps) for node_id, deps in (edges or {}).items()}
        for node_id, node in nodes.items():
            if isinstance(node, ComputationNode):
                self.nodes[node_id] = node
            else:
                self.nodes[node_id] = ComputationNode(
                    id=node_id,
                    qpu_id="qpu_0",
                    compute_time=0,
                    magic_states_required=node,
                    dependencies=list(self.edges.get(node_id, ())),
                )
        for node_id, deps in self.edges.items():
            if node_id not in self.nodes:
                raise ValidationError(f"unknown DAG node {node_id}")
            for dep in deps:
                if dep not in self.nodes:
                    raise ValidationError(f"unknown dependency {dep}")
            self.nodes[node_id].dependencies = list(deps)
        self.completed: set[str] = set()
        self.running_nodes_by_qpu: dict[str, str] = {}
        self.total_magic_states_consumed = 0
        self.wasted_magic_states = 0
        self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        """Reject dependency graphs containing cycles."""
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            # Standard depth-first cycle detection over dependency edges.
            if node_id in visiting:
                raise ValidationError("DAG contains a cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dep in self.nodes[node_id].dependencies:
                visit(dep)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in self.nodes:
            visit(node_id)

    def ready_nodes(self):
        """Return blocked/ready nodes whose dependencies are complete."""
        return tuple(
            node_id
            for node_id, node in self.nodes.items()
            if node_id not in self.completed
            and node.status in {"blocked", "ready"}
            and all(dep in self.completed for dep in node.dependencies)
        )

    def demand_at(self, time: int) -> int:
        """Compatibility helper returning demand for the first ready node."""
        ready = self.ready_nodes()
        return self.nodes[ready[0]].magic_states_required if ready else 0

    def mark_completed(self, node: str) -> None:
        """Compatibility helper that force-marks a node complete."""
        self.completed.add(node)
        self.nodes[node].status = "complete"

    def step(self, t: int, rng=None) -> None:
        """Start ready nodes, advance compute time, and finish satisfied nodes."""
        for node_id in self.ready_nodes():
            node = self.nodes[node_id]
            if node.qpu_id not in self.running_nodes_by_qpu:
                # Version one schedules the first ready node on each available
                # QPU. Later schedulers can replace this without changing the
                # simulator interface.
                node.status = "running"
                node.start_time = t if node.start_time is None else node.start_time
                self.running_nodes_by_qpu[node.qpu_id] = node_id
        for qpu_id, node_id in list(self.running_nodes_by_qpu.items()):
            node = self.nodes[node_id]
            if node.remaining_compute_time and node.remaining_compute_time > 0:
                node.remaining_compute_time -= 1
            # A node is complete only once both local compute and magic-state
            # demand are satisfied.
            if (node.remaining_compute_time or 0) <= 0 and (node.remaining_magic_states or 0) <= 0:
                node.status = "complete"
                node.finish_time = t
                self.completed.add(node.id)
                del self.running_nodes_by_qpu[qpu_id]
            elif (node.remaining_compute_time or 0) <= 0:
                node.status = "waiting_for_magic_states"
            elif (node.remaining_magic_states or 0) > 0:
                node.status = "running_waiting"

    def get_active_requests(self, t: int) -> list[MagicStateRequest]:
        """Return magic-state requests for currently running DAG nodes."""
        requests: list[MagicStateRequest] = []
        for node_id in self.running_nodes_by_qpu.values():
            node = self.nodes[node_id]
            if (node.remaining_magic_states or 0) > 0:
                requests.append(
                    MagicStateRequest(
                        qpu_id=node.qpu_id,
                        n_states=node.remaining_magic_states or 0,
                        request_id=f"node_{node.id}_request",
                        metadata={"node_id": node.id},
                    )
                )
        return requests

    def receive_magic_states(self, qpu_id: str, n: int, t: int) -> None:
        """Apply delivered states to the node running on the target QPU."""
        validate_non_negative_int(n, "n")
        node_id = self.running_nodes_by_qpu.get(qpu_id)
        if node_id is None:
            self.wasted_magic_states += n
            return
        node = self.nodes[node_id]
        consumed = min(n, node.remaining_magic_states or 0)
        node.remaining_magic_states = (node.remaining_magic_states or 0) - consumed
        self.total_magic_states_consumed += consumed
        self.wasted_magic_states += n - consumed

    def is_complete(self) -> bool:
        """Return whether every DAG node has completed."""
        return len(self.completed) == len(self.nodes)

    def completed_work_count(self) -> int:
        """Return how many DAG nodes have completed."""
        return len(self.completed)

    def throughput(self, t: int) -> float:
        """Return completed DAG nodes per elapsed simulation step."""
        return len(self.completed) / max(1, t + 1)

    def update_params(self, **kwargs) -> None:
        """DAG structure is immutable after construction in this implementation."""
        raise AttributeError("DAGComputation parameters are not mutable in place")

    def snapshot(self) -> dict:
        """Return a serializable summary of DAG runtime state."""
        return {
            "completed": sorted(self.completed),
            "running_nodes_by_qpu": dict(self.running_nodes_by_qpu),
            "nodes": {node_id: node.__dict__.copy() for node_id, node in self.nodes.items()},
        }
