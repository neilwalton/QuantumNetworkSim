from magic_state_sim import FiniteMemory, FixedPeriodicComputation, LossyNetwork, MagicStateFactory, MagicStateSimulator, QPU, QPUCommunicationMemory

def test_simulator_runs_and_collects_stats():
    sim = MagicStateSimulator(
        factory=MagicStateFactory(production_rate=1),
        source_memory=FiniteMemory(4),
        qpus=[QPU('q', QPUCommunicationMemory(4))],
        network=LossyNetwork(latency=0),
        computation=FixedPeriodicComputation(period=1),
    )
    stats = sim.run(3)
    assert stats.produced == 3
    assert stats.delivered == 3
    assert stats.completed_operations >= 1
