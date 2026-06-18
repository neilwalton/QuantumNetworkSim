"""Scheduling and admission policies."""
from __future__ import annotations
from dataclasses import dataclass
import random
from .tokens import MagicStateToken, validate_probability

class StoragePolicy:
    def admit(self, tokens, memory, time:int): return tuple(tokens)

@dataclass
class DropNewestOnOverflow(StoragePolicy):
    def admit(self, tokens, memory, time:int): return tuple(tokens)[:memory.remaining_capacity]

@dataclass
class DropOldestOnOverflow(StoragePolicy):
    def admit(self, tokens, memory, time:int):
        tokens=tuple(tokens); overflow=max(0, len(tokens)-memory.remaining_capacity)
        if overflow: memory.discard_oldest(overflow)
        return tokens[:memory.remaining_capacity]

class RoutingPolicy:
    def select_destination(self, destinations, token:MagicStateToken, time:int):
        return destinations[0] if destinations else None

class RoundRobinRoutingPolicy(RoutingPolicy):
    def __init__(self): self._index=0
    def select_destination(self, destinations, token, time:int):
        if not destinations: return None
        dest=destinations[self._index % len(destinations)]; self._index += 1; return dest

@dataclass
class RandomRoutingPolicy(RoutingPolicy):
    seed: int | None = None
    def __post_init__(self): self._rng=random.Random(self.seed)
    def select_destination(self, destinations, token, time:int): return self._rng.choice(list(destinations)) if destinations else None

@dataclass
class ConsumptionPolicy:
    tokens_per_operation: int = 1
