import pytest

from magic_state_sim import ComputationNode, DAGComputation, FixedPeriodicComputation, ValidationError


def test_fixed_periodic_requests_stalls_and_completion():
    c = FixedPeriodicComputation(qpu_id="q", interval=2, magic_states_per_round=3, start_time=1)
    assert [c.demand_at(t) for t in range(5)] == [0, 3, 0, 3, 0]
    c.step(0)
    assert c.get_active_requests(0) == []
    c.step(1)
    request = c.get_active_requests(1)[0]
    assert request.qpu_id == "q"
    assert request.n_states == 3
    assert c.stall_time == 1
    c.receive_magic_states("q", 2, 1)
    assert c.get_active_requests(1)[0].n_states == 1
    c.receive_magic_states("q", 1, 1)
    c.step(1)
    assert c.completed_rounds == 1
    assert c.throughput(1) == 0.5


def test_fixed_periodic_failure_mode():
    c = FixedPeriodicComputation(qpu_id="q", interval=1, magic_states_per_round=1, allow_failure=True, failure_after_stall=1)
    c.step(0)
    assert c.failed


def test_dag_readiness_cycle_rejection_and_completion():
    with pytest.raises(ValidationError):
        DAGComputation(
            nodes={"a": 1, "b": 1},
            edges={"a": ("b",), "b": ("a",)},
        )

    c = DAGComputation(nodes={"a": 1, "b": 2}, edges={"b": ("a",)})
    assert c.ready_nodes() == ("a",)
    assert c.demand_at(0) == 1
    c.step(0)
    assert c.get_active_requests(0)[0].n_states == 1
    c.receive_magic_states("qpu_0", 1, 0)
    c.step(0)
    assert "a" in c.completed
    assert c.ready_nodes() == ("b",)


def test_dag_compute_and_magic_both_required():
    node = ComputationNode(id="n", qpu_id="q", compute_time=2, magic_states_required=1)
    c = DAGComputation(nodes={"n": node})
    c.step(0)
    c.receive_magic_states("q", 1, 0)
    assert not c.is_complete()
    c.step(1)
    assert c.is_complete()
