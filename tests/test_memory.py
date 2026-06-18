import pytest
from magic_state_sim import FiniteMemory, MagicStateToken, MemoryFullError, InsufficientTokensError

def test_finite_memory_fifo_and_capacity():
    mem = FiniteMemory(1)
    token = MagicStateToken(0)
    mem.add([token])
    assert mem.available == 1
    with pytest.raises(MemoryFullError):
        mem.add([MagicStateToken(1)])
    assert mem.take(1) == (token,)
    with pytest.raises(InsufficientTokensError):
        mem.take(1)
