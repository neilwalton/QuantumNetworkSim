from magic_state_sim import DropNewestOnOverflow, DropOldestOnOverflow, FiniteMemory, MagicStateToken, RoundRobinRoutingPolicy

def test_drop_newest_limits_admission():
    mem = FiniteMemory(1)
    assert len(DropNewestOnOverflow().admit([MagicStateToken(0), MagicStateToken(0)], mem, 0)) == 1

def test_drop_oldest_makes_room():
    mem = FiniteMemory(1); old = MagicStateToken(0); new = MagicStateToken(1)
    mem.add([old])
    admitted = DropOldestOnOverflow().admit([new], mem, 1)
    mem.add(admitted)
    assert mem.peek() == (new,)

def test_round_robin_policy():
    p = RoundRobinRoutingPolicy()
    assert [p.select_destination(['a','b'], MagicStateToken(0), 0) for _ in range(3)] == ['a','b','a']
