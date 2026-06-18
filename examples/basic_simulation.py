"""Run a basic magic-state simulation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magic_state_sim import (
    FiniteMemory,
    FixedPeriodicComputation,
    LossyNetwork,
    MagicStateFactory,
    MagicStateSimulator,
    QPU,
    QPUCommunicationMemory,
)


def main() -> None:
    simulator = MagicStateSimulator(
        factory=MagicStateFactory(production_rate=2, period=1),
        source_memory=FiniteMemory(capacity=8),
        qpus=[QPU("qpu-0", QPUCommunicationMemory(capacity=8))],
        network=LossyNetwork(loss_probability=0.1, latency=1, seed=7),
        computation=FixedPeriodicComputation(period=2, tokens_per_operation=1),
    )
    print(simulator.run(10).as_dict())


if __name__ == "__main__":
    main()
