import numpy as np

from magic_state_sim import FiniteMemory, LossyNetwork, MagicState, MagicStateToken, NetworkEdge, QPU, QPUCommunicationMemory


def test_bell_pair_creation_success_probability_and_update():
    rng = np.random.default_rng(0)
    qpu = QPU("q")
    net = LossyNetwork()
    net.add_edge(NetworkEdge(source_id="m", target_id="q", bell_pair_success_probability=0.0))
    assert net.establish_bell_pairs("m", qpu, 3, 0, rng) == []
    net.update_edge_params("m", "q", bell_pair_success_probability=1.0)
    assert len(net.establish_bell_pairs("m", qpu, 3, 1, rng)) == 3


def test_teleport_success_failure_and_no_resource_cases():
    rng = np.random.default_rng(0)
    mem = FiniteMemory(id="m", capacity=3)
    qpu = QPU("q")
    net = LossyNetwork()
    net.add_edge(NetworkEdge(source_id="m", target_id="q", teleport_success_probability=1.0))
    mem.add_many([MagicState(id="s0", created_at=0)], t=0, rng=rng)
    assert net.teleport(mem, qpu, 1, 0, rng) == []
    net.establish_bell_pairs("m", qpu, 1, 0, rng)
    delivered = net.teleport(mem, qpu, 1, 0, rng)
    assert [s.id for s in delivered] == ["s0"]

    mem.add_many([MagicState(id="s1", created_at=1)], t=1, rng=rng)
    net.establish_bell_pairs("m", qpu, 1, 1, rng)
    net.update_edge_params("m", "q", teleport_success_probability=0.0)
    assert net.teleport(mem, qpu, 1, 1, rng) == []
    assert mem.list() == []


def test_latency_zero_and_positive():
    rng = np.random.default_rng(0)
    mem = FiniteMemory(id="m", capacity=2)
    qpu = QPU("q")
    net = LossyNetwork()
    net.add_edge(NetworkEdge(source_id="m", target_id="q", latency=2))
    mem.add_many([MagicState(id="s0", created_at=0)], t=0, rng=rng)
    net.establish_bell_pairs("m", qpu, 1, 0, rng)
    assert net.teleport(mem, qpu, 1, 0, rng) == []
    assert net.step(1, rng) == []
    assert [(qid, state.id) for qid, state in net.step(2, rng)] == [("q", "s0")]


def test_compat_direct_network_send():
    qpu = QPU("q", QPUCommunicationMemory(2))
    net = LossyNetwork(latency=2)
    token = MagicStateToken(0)
    assert net.send(token, qpu, 0)
    assert net.tick(1) == ()
    assert net.tick(2) == (token,)
    assert qpu.memory.available == 1

    lossy = LossyNetwork(loss_probability=1.0)
    assert not lossy.send(MagicStateToken(0), qpu, 0)
    assert lossy.lost == 1
