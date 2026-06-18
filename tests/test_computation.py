from magic_state_sim import DAGComputation, FixedPeriodicComputation

def test_fixed_periodic_computation():
    c = FixedPeriodicComputation(period=2, tokens_per_operation=3, start_time=1)
    assert [c.demand_at(t) for t in range(5)] == [0,3,0,3,0]

def test_dag_computation_readiness():
    c = DAGComputation(nodes={'a':1,'b':2}, edges={'b':('a',)})
    assert c.ready_nodes() == ('a',)
    assert c.demand_at(0) == 1
    c.mark_completed('a')
    assert c.ready_nodes() == ('b',)
