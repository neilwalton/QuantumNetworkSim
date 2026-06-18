import numpy as np

from magic_state_sim import (
    DefaultDropPolicy,
    DropNewestOnOverflow,
    DropOldestOnOverflow,
    DropOldestPolicy,
    DropRandomPolicy,
    FiniteMemory,
    MagicState,
    MagicStateToken,
    OldestFirstSelectionPolicy,
    RoundRobinRoutingPolicy,
)


def test_default_drop_policy_prefers_lowest_fidelity_then_oldest():
    rng = np.random.default_rng(0)
    old = MagicState(id="old", created_at=0)
    low = MagicState(id="low", created_at=1, fidelity=0.1)
    high = MagicState(id="high", created_at=2, fidelity=0.9)
    assert DefaultDropPolicy().select([old, low, high], t=3, rng=rng) is low
    assert DropOldestPolicy().select([old, high], t=3, rng=rng) is old


def test_random_and_oldest_selection_policies():
    rng = np.random.default_rng(0)
    states = [MagicState(id=f"s{i}", created_at=i) for i in range(3)]
    assert DropRandomPolicy().select(states, t=0, rng=rng) in states
    assert [s.id for s in OldestFirstSelectionPolicy().select(states[::-1], 2, t=0, rng=rng)] == ["s0", "s1"]


def test_compat_overflow_and_routing_policies():
    mem = FiniteMemory(1)
    assert len(DropNewestOnOverflow().admit([MagicStateToken(0), MagicStateToken(0)], mem, 0)) == 1
    old = MagicStateToken(0)
    new = MagicStateToken(1)
    mem.add([old])
    admitted = DropOldestOnOverflow().admit([new], mem, 1)
    mem.add(admitted)
    assert mem.peek() == (new,)
    p = RoundRobinRoutingPolicy()
    assert [p.select_destination(["a", "b"], MagicStateToken(0), 0) for _ in range(3)] == ["a", "b", "a"]
