"""Simulation statistics."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SimulationStats:
    produced: int = 0
    admitted: int = 0
    sent: int = 0
    delivered: int = 0
    lost: int = 0
    consumed: int = 0
    failed_operations: int = 0
    completed_operations: int = 0
    def as_dict(self): return self.__dict__.copy()
