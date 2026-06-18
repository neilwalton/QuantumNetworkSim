"""Magic-state factory models."""
from __future__ import annotations
from dataclasses import dataclass
from .tokens import MagicStateToken, validate_positive_int, validate_probability

@dataclass
class MagicStateFactory:
    production_rate: int = 1
    period: int = 1
    fidelity: float = 1.0
    source: str = "factory"

    def __post_init__(self):
        validate_positive_int(self.production_rate,"production_rate"); validate_positive_int(self.period,"period"); validate_probability(self.fidelity,"fidelity")
    def produce(self, time:int) -> tuple[MagicStateToken, ...]:
        if time % self.period != 0: return ()
        return tuple(MagicStateToken(produced_at=time, fidelity=self.fidelity, source=self.source) for _ in range(self.production_rate))
