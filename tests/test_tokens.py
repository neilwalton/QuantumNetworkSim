import pytest

from magic_state_sim import (
    BellPair,
    IdGenerator,
    MagicState,
    MagicStateToken,
    TokenBatch,
    ValidationError,
    ensure_tokens,
)


def test_magic_state_flags_age_and_compat_token():
    state = MagicState(id="s0", created_at=2, fidelity=0.9)
    state.mark("in_memory")
    assert state.age(5) == 3
    assert state.has_flag("in_memory")

    token = MagicStateToken(produced_at=2, fidelity=0.9, source="factory")
    assert token.age_at(5) == 3
    assert token.produced_at == 2
    assert token.source == "factory"


def test_bell_pair_and_id_generator():
    ids = IdGenerator("bp")
    assert ids.new() == "bp_1"
    pair = BellPair(id=ids.new(), source_id="m", target_qpu_id="q", created_at=0)
    assert pair.id == "bp_2"
    assert pair.age(3) == 3


def test_batch_and_validation():
    state = MagicState(id="s0", created_at=0)
    batch = TokenBatch([state])
    taken, rest = batch.take(1)
    assert taken == (state,)
    assert len(rest) == 0
    with pytest.raises(ValidationError):
        MagicState(id="bad", created_at=0, fidelity=1.5)
    with pytest.raises(ValidationError):
        ensure_tokens([], minimum=1)
