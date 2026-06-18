"""Finite FIFO memory models."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from .exceptions import InsufficientTokensError, MemoryFullError
from .tokens import MagicStateToken, validate_positive_int, validate_non_negative_int

@dataclass
class FiniteMemory:
    capacity: int
    _tokens: deque[MagicStateToken] = field(default_factory=deque, init=False, repr=False)

    def __post_init__(self): validate_positive_int(self.capacity, "capacity")
    def __len__(self): return len(self._tokens)
    @property
    def available(self) -> int: return len(self._tokens)
    @property
    def remaining_capacity(self) -> int: return self.capacity - len(self._tokens)
    def peek(self) -> tuple[MagicStateToken, ...]: return tuple(self._tokens)
    def clear(self) -> None: self._tokens.clear()
    def add(self, tokens):
        tokens = tuple(tokens)
        if len(tokens) > self.remaining_capacity: raise MemoryFullError("memory capacity exceeded")
        self._tokens.extend(tokens); return len(tokens)
    def discard_oldest(self, count:int=1):
        validate_non_negative_int(count,"count")
        removed=[]
        for _ in range(min(count,len(self._tokens))): removed.append(self._tokens.popleft())
        return tuple(removed)
    def take(self, count:int=1):
        validate_non_negative_int(count,"count")
        if len(self._tokens) < count: raise InsufficientTokensError("not enough tokens in memory")
        return tuple(self._tokens.popleft() for _ in range(count))

class QPUCommunicationMemory(FiniteMemory):
    """Finite memory used as a QPU receive buffer."""
