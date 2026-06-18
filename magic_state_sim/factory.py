"""Magic-state factory models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .tokens import (
    IdGenerator,
    MagicState,
    MagicStateToken,
    validate_positive_int,
    validate_positive_number,
    validate_probability,
)


@dataclass
class BernoulliMagicStateFactory:
    """Stochastic factory that attempts independent productions each step."""

    id: str
    attached_memory_id: str | None
    production_probability: float
    output_occupancy: int | float = 1
    output_fidelity: float | None = None
    max_output_per_step: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id_gen = IdGenerator(f"{self.id}_state")
        self.validate()

    def validate(self) -> None:
        """Check factory parameters before a run or after a parameter update."""
        if not self.id:
            raise ValueError("id must be non-empty")
        self.production_probability = validate_probability(
            self.production_probability, "production_probability"
        )
        validate_positive_number(self.output_occupancy, "output_occupancy")
        if self.output_fidelity is not None:
            self.output_fidelity = validate_probability(self.output_fidelity, "output_fidelity")
        validate_positive_int(self.max_output_per_step, "max_output_per_step")

    def step(self, t: int, rng) -> list[MagicState]:
        """Attempt stochastic production at time ``t`` and return new states."""
        states: list[MagicState] = []
        for _ in range(self.max_output_per_step):
            if rng.random() < self.production_probability:
                states.append(
                    MagicState(
                        id=self.id_gen.new(),
                        created_at=t,
                        occupancy=self.output_occupancy,
                        fidelity=self.output_fidelity,
                        metadata={"factory_id": self.id, **self.metadata},
                    )
                )
        return states

    def update_params(self, **kwargs) -> None:
        """Strictly update known parameters and revalidate the factory."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.validate()

    def snapshot(self) -> dict:
        """Return a serializable summary of factory configuration."""
        return {
            "id": self.id,
            "attached_memory_id": self.attached_memory_id,
            "production_probability": self.production_probability,
            "output_occupancy": self.output_occupancy,
            "output_fidelity": self.output_fidelity,
            "max_output_per_step": self.max_output_per_step,
            "metadata": dict(self.metadata),
        }


@dataclass
class MagicStateFactory:
    """Backward-compatible deterministic periodic factory."""

    production_rate: int = 1
    period: int = 1
    fidelity: float = 1.0
    source: str = "factory"

    def __post_init__(self) -> None:
        """Validate the older deterministic factory parameters."""
        validate_positive_int(self.production_rate, "production_rate")
        validate_positive_int(self.period, "period")
        validate_probability(self.fidelity, "fidelity")
        if not self.source:
            raise ValueError("source must be non-empty")

    def produce(self, time: int) -> tuple[MagicStateToken, ...]:
        """Produce tokens on period-aligned time steps for compatibility code."""
        if time % self.period != 0:
            return ()
        return tuple(
            MagicStateToken(produced_at=time, fidelity=self.fidelity, source=self.source)
            for _ in range(self.production_rate)
        )

    def step(self, t: int, rng=None) -> list[MagicStateToken]:
        """Adapter used by the new Simulator, delegating to ``produce``."""
        return list(self.produce(t))

    def update_params(self, **kwargs) -> None:
        """Strictly update compatibility factory parameters."""
        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise AttributeError(f"{self.__class__.__name__} has no parameter {key}")
            setattr(self, key, value)
        self.__post_init__()

    def snapshot(self) -> dict:
        """Return a serializable summary of compatibility factory settings."""
        return {
            "production_rate": self.production_rate,
            "period": self.period,
            "fidelity": self.fidelity,
            "source": self.source,
        }
