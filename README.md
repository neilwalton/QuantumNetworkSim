# QuantumNetworkSim

`magic_state_sim` is a small discrete-time simulator for magic-state production,
storage, Bell-pair-mediated teleportation, QPU delivery, and computation demand.

The core architecture is:

```text
Factory -> Memory -> Network -> QPU -> Computation
```

Components do not call each other directly. A central `Simulator` coordinates
each time step so factories, memories, networks, QPUs, and computation models can
later be replaced independently.

## Minimal Example

```python
from magic_state_sim import (
    BernoulliMagicStateFactory,
    FiniteMemory,
    FixedPeriodicComputation,
    LossyNetwork,
    NetworkEdge,
    QPU,
    Simulator,
)

factory = BernoulliMagicStateFactory(
    id="factory_0",
    attached_memory_id="memory_0",
    production_probability=0.8,
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
print(stats.counters)
```

## Compatibility

The original small API remains available for simple scripts:

```python
from magic_state_sim import MagicStateFactory, MagicStateSimulator
```

Those names are compatibility adapters. New code should prefer
`BernoulliMagicStateFactory` and `Simulator`.
