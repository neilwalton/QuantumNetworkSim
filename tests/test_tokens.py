import pytest
from magic_state_sim import MagicStateToken, TokenBatch, ValidationError, ensure_tokens

def test_token_age_and_batch():
    token = MagicStateToken(produced_at=2, fidelity=0.9)
    assert token.age_at(5) == 3
    batch = TokenBatch([token])
    taken, rest = batch.take(1)
    assert taken == (token,)
    assert len(rest) == 0

def test_validation_rejects_bad_probability():
    with pytest.raises(ValidationError):
        MagicStateToken(produced_at=0, fidelity=1.5)
    with pytest.raises(ValidationError):
        ensure_tokens([], minimum=1)
