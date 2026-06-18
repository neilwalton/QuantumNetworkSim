from magic_state_sim import (
    BernoulliMagicStateFactory,
    FiniteMemory,
    FixedPeriodicComputation,
    LossyNetwork,
    MagicStateFactory,
    MagicStateSimulator,
    NetworkEdge,
    QPU,
    QPUCommunicationMemory,
    Simulator,
)


def build_simple_sim(seed=123, production_probability=1.0):
    factory = BernoulliMagicStateFactory(
        id="factory_0",
        attached_memory_id="memory_0",
        production_probability=production_probability,
    )
    memory = FiniteMemory(id="memory_0", capacity=10)
    qpu = QPU(id="qpu_0")
    network = LossyNetwork()
    network.add_edge(
        NetworkEdge(
            source_id="memory_0",
            target_id="qpu_0",
            bell_pair_success_probability=1.0,
            teleport_success_probability=1.0,
        )
    )
    computation = FixedPeriodicComputation(qpu_id="qpu_0", interval=1, magic_states_per_round=1)
    return Simulator(
        factories={"factory_0": factory},
        memories={"memory_0": memory},
        network=network,
        qpus={"qpu_0": qpu},
        computation=computation,
        factory_memory_map={"factory_0": "memory_0"},
        qpu_memory_map={"qpu_0": "memory_0"},
        seed=seed,
    )


def test_simulator_perfect_path_stats_and_capacity():
    sim = build_simple_sim()
    stats = sim.run(3)
    assert stats.counters["states_created"] == 3
    assert stats.counters["states_delivered"] == 3
    assert stats.counters["completed_operations"] == 3
    assert all(row["memory_occupancy"]["memory_0"] <= 10 for row in stats.history)


def test_simulator_reproducibility_and_zero_production_stall():
    sim1 = build_simple_sim(seed=7, production_probability=0.5)
    sim2 = build_simple_sim(seed=7, production_probability=0.5)
    assert sim1.run(10).as_dict() == sim2.run(10).as_dict()

    stalled = build_simple_sim(production_probability=0.0)
    stalled.run(3)
    assert stalled.computation.completed_rounds == 0
    assert stalled.computation.stall_time == 3


def test_compat_magic_state_simulator_runs():
    sim = MagicStateSimulator(
        factory=MagicStateFactory(production_rate=1),
        source_memory=FiniteMemory(4),
        qpus=[QPU("q", QPUCommunicationMemory(4))],
        network=LossyNetwork(latency=0),
        computation=FixedPeriodicComputation(period=1),
    )
    stats = sim.run(3)
    assert stats.produced == 3
    assert stats.delivered == 3
    assert stats.completed_operations >= 1
