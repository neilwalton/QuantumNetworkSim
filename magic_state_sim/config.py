"""Configuration helpers."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SimulationConfig:
    duration: int = 100
    factory_rate: int = 1
    factory_period: int = 1
    memory_capacity: int = 16
    network_loss_probability: float = 0.0
    network_latency: int = 0
