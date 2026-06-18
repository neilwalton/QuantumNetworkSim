import pytest
from magic_state_sim import InsufficientTokensError, MagicStateToken, QPU, QPUCommunicationMemory

def test_qpu_execute_consumes_tokens():
    qpu = QPU('q', QPUCommunicationMemory(2))
    qpu.receive([MagicStateToken(0)])
    assert len(qpu.execute(1)) == 1
    assert qpu.consumed_tokens == 1
    with pytest.raises(InsufficientTokensError):
        qpu.execute(1)
