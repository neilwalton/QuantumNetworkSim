from magic_state_sim import LossyNetwork, MagicStateToken, QPU, QPUCommunicationMemory

def test_network_delivers_after_latency():
    qpu = QPU('q', QPUCommunicationMemory(2))
    net = LossyNetwork(latency=2)
    token = MagicStateToken(0)
    assert net.send(token, qpu, 0)
    assert net.tick(1) == ()
    assert net.tick(2) == (token,)
    assert qpu.memory.available == 1

def test_network_loss():
    qpu = QPU('q')
    net = LossyNetwork(loss_probability=1.0)
    assert not net.send(MagicStateToken(0), qpu, 0)
    assert net.lost == 1
