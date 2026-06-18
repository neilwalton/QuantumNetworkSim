from magic_state_sim import MagicStateFactory

def test_factory_periodic_production():
    factory = MagicStateFactory(production_rate=2, period=3)
    assert len(factory.produce(0)) == 2
    assert factory.produce(1) == ()
    assert len(factory.produce(3)) == 2
