import numpy as np
import pytest

from magic_state_sim import BernoulliMagicStateFactory, MagicStateFactory, ValidationError


def test_bernoulli_probability_extremes_and_fields():
    rng = np.random.default_rng(1)
    factory = BernoulliMagicStateFactory(
        id="f",
        attached_memory_id="m",
        production_probability=0.0,
        output_occupancy=2,
        output_fidelity=0.95,
        max_output_per_step=3,
    )
    assert factory.step(0, rng) == []
    factory.update_params(production_probability=1.0)
    states = factory.step(1, rng)
    assert len(states) == 3
    assert states[0].occupancy == 2
    assert states[0].fidelity == 0.95


def test_factory_invalid_probability():
    with pytest.raises(ValidationError):
        BernoulliMagicStateFactory("f", "m", 1.2)


def test_compat_periodic_factory():
    factory = MagicStateFactory(production_rate=2, period=3)
    assert len(factory.produce(0)) == 2
    assert factory.produce(1) == ()
    assert len(factory.step(3)) == 2
