"""Run a basic planned magic-state simulation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from magic_state_sim import (
    BernoulliMagicStateFactory,
    FiniteMemory,
    FixedPeriodicComputation,
    LossyNetwork,
    NetworkEdge,
    QPU,
    Simulator,
)


def main() -> None:
    factory = BernoulliMagicStateFactory(
        id="factory_0",
        attached_memory_id="memory_0",
        production_probability=0.8,
        output_occupancy=1,
        output_fidelity=0.99,
    )
    memory = FiniteMemory(id="memory_0", capacity=50, decoherence_probability=0.01)
    qpu = QPU(id="qpu_0")
    network = LossyNetwork()
    network.add_edge(
        NetworkEdge(
            source_id="memory_0",
            target_id="qpu_0",
            bell_pair_success_probability=0.9,
            teleport_success_probability=1.0,
            latency=0,
        )
    )
    computation = FixedPeriodicComputation(
        qpu_id="qpu_0",
        interval=10,
        magic_states_per_round=5,
    )
    sim = Simulator(
        factories={"factory_0": factory},
        memories={"memory_0": memory},
        network=network,
        qpus={"qpu_0": qpu},
        computation=computation,
        factory_memory_map={"factory_0": "memory_0"},
        qpu_memory_map={"qpu_0": "memory_0"},
        seed=123,
    )
    stats = sim.run(1000)
    print(stats.as_dict())

    try:
        df = stats.to_dataframe()
    except ImportError:
        return
    print(df.tail())


if __name__ == "__main__":
    main()
