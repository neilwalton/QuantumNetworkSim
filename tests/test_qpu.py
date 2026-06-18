import numpy as np
import pytest

from magic_state_sim import BellPair, InsufficientTokensError, MagicStateToken, QPU, QPUCommunicationMemory


def test_qpu_bell_pair_capacity_source_filter_and_decoherence():
    rng = np.random.default_rng(0)
    qpu = QPU("q", bell_pair_capacity=1, bell_pair_decoherence_probability=0.0)
    bp1 = BellPair(id="bp1", source_id="m1", target_qpu_id="q", created_at=0)
    bp2 = BellPair(id="bp2", source_id="m2", target_qpu_id="q", created_at=1)
    assert qpu.add_bell_pair(bp1, t=0, rng=rng)
    assert qpu.add_bell_pair(bp2, t=1, rng=rng)
    assert bp1.has_flag("dropped")
    assert qpu.available_bell_pairs("m2") == 1
    assert qpu.consume_bell_pair("m1") is None
    assert qpu.consume_bell_pair("m2") is bp2

    qpu.add_bell_pair(BellPair(id="bp3", source_id="m", target_qpu_id="q", created_at=2), t=2, rng=rng)
    qpu.update_params(bell_pair_decoherence_probability=1.0)
    qpu.step(3, rng)
    assert qpu.available_bell_pairs() == 0


def test_qpu_infinite_capacity_and_compat_execute():
    qpu = QPU("q", QPUCommunicationMemory(2))
    qpu.receive([MagicStateToken(0)])
    assert len(qpu.execute(1)) == 1
    assert qpu.consumed_tokens == 1
    with pytest.raises(InsufficientTokensError):
        qpu.execute(1)

    qpu = QPU("q2")
    for i in range(20):
        assert qpu.add_bell_pair(BellPair(id=f"bp{i}", source_id="m", target_qpu_id="q2", created_at=i))
    assert qpu.available_bell_pairs() == 20
