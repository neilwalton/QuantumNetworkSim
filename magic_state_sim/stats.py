"""Simulation statistics."""
from __future__ import annotations

from collections import defaultdict


class SimulationStats:
    """Cumulative counters and per-step simulator history."""

    _compat_keys = {
        "produced": "states_created",
        "admitted": "states_accepted_by_memory",
        "sent": "teleport_attempts",
        "delivered": "states_delivered",
        "lost": "states_lost",
        "consumed": "states_consumed",
        "failed_operations": "failed_operations",
        "completed_operations": "completed_operations",
    }

    def __init__(self) -> None:
        object.__setattr__(self, "counters", defaultdict(int))
        object.__setattr__(self, "history", [])

    def __getattr__(self, name: str):
        if name in self._compat_keys:
            return self.counters[self._compat_keys[name]]
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name in self._compat_keys:
            self.counters[self._compat_keys[name]] = value
        else:
            object.__setattr__(self, name, value)

    def inc(self, key: str, amount: int = 1) -> None:
        self.counters[key] += amount

    def record_step(self, t: int, simulator, *, delivered_by_qpu: dict[str, int] | None = None) -> None:
        computation = simulator.computation
        completed_work = (
            computation.completed_work_count()
            if hasattr(computation, "completed_work_count")
            else 0
        )
        throughput = computation.throughput(t) if hasattr(computation, "throughput") else 0.0
        self.history.append(
            {
                "t": t,
                "memory_occupancy": {
                    mid: mem.occupancy() for mid, mem in simulator.memories.items()
                },
                "memory_count": {mid: len(mem.list()) for mid, mem in simulator.memories.items()},
                "qpu_bell_pairs": {
                    qid: qpu.available_bell_pairs() for qid, qpu in simulator.qpus.items()
                },
                "active_requests": [
                    request.__dict__.copy()
                    for request in getattr(simulator, "_last_requests", [])
                ],
                "delivered_states_by_qpu": dict(delivered_by_qpu or {}),
                "completed_work": completed_work,
                "throughput": throughput,
            }
        )

    def as_dict(self) -> dict:
        result = dict(self.counters)
        for old_name, counter_name in self._compat_keys.items():
            result[old_name] = self.counters[counter_name]
        return result

    def to_dataframe(self):
        import pandas as pd

        return pd.DataFrame(self.history)
