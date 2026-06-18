"""Lossy fixed-latency network."""
from __future__ import annotations
from dataclasses import dataclass, field
import random
from .exceptions import MemoryFullError
from .tokens import MagicStateToken, validate_non_negative_int, validate_probability

@dataclass
class LossyNetwork:
    loss_probability: float = 0.0
    latency: int = 0
    seed: int | None = None
    _in_flight: list[tuple[int, object, MagicStateToken]] = field(default_factory=list, init=False, repr=False)
    delivered: int = 0
    lost: int = 0
    def __post_init__(self):
        validate_probability(self.loss_probability,"loss_probability"); validate_non_negative_int(self.latency,"latency"); self._rng=random.Random(self.seed)
    def send(self, token:MagicStateToken, destination, time:int) -> bool:
        if self._rng.random() < self.loss_probability:
            self.lost += 1; return False
        self._in_flight.append((time+self.latency, destination, token)); return True
    def tick(self, time:int):
        ready=[]; pending=[]
        for item in self._in_flight:
            (arrival,dest,token)=item
            (ready if arrival <= time else pending).append(item)
        self._in_flight=pending
        delivered_tokens = []
        for _, dest, token in ready:
            try:
                dest.receive((token,))
            except MemoryFullError:
                self.lost += 1
            else:
                self.delivered += 1
                delivered_tokens.append(token)
        return tuple(delivered_tokens)
