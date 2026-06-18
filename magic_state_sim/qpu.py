"""QPU model with communication memory."""
from __future__ import annotations
from dataclasses import dataclass, field
from .memory import QPUCommunicationMemory
from .exceptions import InsufficientTokensError
from .tokens import validate_positive_int

@dataclass
class QPU:
    name: str
    memory: QPUCommunicationMemory = field(default_factory=lambda: QPUCommunicationMemory(16))
    consumed_tokens: int = 0
    failed_operations: int = 0
    completed_operations: int = 0
    def receive(self, tokens): return self.memory.add(tokens)
    def can_execute(self, tokens_required:int=1) -> bool:
        validate_positive_int(tokens_required,"tokens_required"); return self.memory.available >= tokens_required
    def execute(self, tokens_required:int=1):
        if not self.can_execute(tokens_required):
            self.failed_operations += 1; raise InsufficientTokensError("QPU lacks required magic-state tokens")
        tokens=self.memory.take(tokens_required); self.consumed_tokens += len(tokens); self.completed_operations += 1; return tokens
