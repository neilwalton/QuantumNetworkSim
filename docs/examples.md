# Examples

## Planned API

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
print(stats.counters)
```

## Compatibility API

```python
from magic_state_sim import (
    FiniteMemory,
    FixedPeriodicComputation,
    LossyNetwork,
    MagicStateFactory,
    MagicStateSimulator,
    QPU,
    QPUCommunicationMemory,
)

sim = MagicStateSimulator(
    factory=MagicStateFactory(production_rate=2),
    source_memory=FiniteMemory(8),
    qpus=[QPU("qpu-0", QPUCommunicationMemory(8))],
    network=LossyNetwork(loss_probability=0.1, latency=1, seed=7),
    computation=FixedPeriodicComputation(period=2),
)

print(sim.run(10).as_dict())
```

## Updating Parameters Mid-Simulation

```python
sim.update_component_params(
    component_type="factory",
    component_id="factory_0",
    production_probability=0.95,
)

sim.update_component_params(
    component_type="network_edge",
    component_id="memory_0->qpu_0",
    teleport_success_probability=0.8,
)
```

## Inspecting Results

```python
snapshot = sim.snapshot()
print(snapshot["memories"])

history = sim.stats.history
print(history[-1])

df = sim.stats.to_dataframe()  # requires pandas
```
