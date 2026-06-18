import numpy as np
import pytest

from magic_state_sim import (
    DropOldestPolicy,
    FiniteMemory,
    InsufficientTokensError,
    MagicState,
    MagicStateToken,
    MemoryFullError,
)


def test_memory_occupancy_capacity_and_drop_lowest_fidelity():
    rng = np.random.default_rng(0)
    mem = FiniteMemory(id="m", capacity=2)
    low = MagicState(id="low", created_at=0, fidelity=0.1)
    high = MagicState(id="high", created_at=0, fidelity=0.9)
    new = MagicState(id="new", created_at=1, fidelity=0.5)
    assert mem.add(low, t=0, rng=rng)
    assert mem.add(high, t=0, rng=rng)
    assert mem.add(new, t=1, rng=rng)
    assert low.has_flag("dropped")
    assert {s.id for s in mem.list()} == {"high", "new"}


def test_too_large_rejected_and_capacity_shrink_enforced():
    rng = np.random.default_rng(0)
    mem = FiniteMemory(id="m", capacity=2, drop_policy=DropOldestPolicy())
    old = MagicState(id="old", created_at=0)
    newer = MagicState(id="new", created_at=1)
    assert not mem.add(MagicState(id="large", created_at=0, occupancy=3), t=0, rng=rng)
    mem.add_many([old, newer], t=0, rng=rng)
    mem.update_params(capacity=1)
    assert old.has_flag("dropped")
    assert [s.id for s in mem.list()] == ["new"]


def test_decoherence_pop_by_id_and_pop_available():
    rng = np.random.default_rng(0)
    mem = FiniteMemory(id="m", capacity=4, decoherence_probability=0.0)
    states = [MagicState(id=f"s{i}", created_at=i) for i in range(3)]
    mem.add_many(states, t=0, rng=rng)
    assert mem.pop_by_id("s1").id == "s1"
    assert [s.id for s in mem.pop_available(5, t=3)] == ["s0", "s2"]
    mem.add_many(states[:2], t=4, rng=rng)
    mem.update_params(decoherence_probability=1.0)
    mem.step(5, rng)
    assert mem.list() == []
    assert all(s.has_flag("decohered") for s in states[:2])


def test_compat_batch_add_is_strict_fifo():
    mem = FiniteMemory(1)
    token = MagicStateToken(0)
    mem.add([token])
    assert mem.available == 1
    with pytest.raises(MemoryFullError):
        mem.add([MagicStateToken(1)])
    assert mem.take(1) == (token,)
    with pytest.raises(InsufficientTokensError):
        mem.take(1)
