# Public API Reference

This reference explains the public objects by module. It is not only a list of
signatures: each entry describes the role of the object and how it participates
in the simulation.

## `tokens.py`

**Role:** token data model and validation helpers.

The token module contains the passive data objects that move through the
simulation. Tokens are intentionally lightweight. They do not know where they
should go next; other components inspect and mutate them.

### `MagicState(id, created_at, occupancy=1, fidelity=None, flags=None, metadata=None)`

Represents one magic state produced by a factory. It may be stored in memory,
teleported over the network, delivered to a QPU, and counted by a computation
model.

Parameters:

- `id`: readable unique identifier for debugging and snapshots.
- `created_at`: integer simulation time when the state was created.
- `occupancy`: amount of memory capacity consumed by this state.
- `fidelity`: optional quality value. Drop policies can use it.
- `flags`: lifecycle markers. Normally leave this empty at construction.
- `metadata`: extension dictionary for experiment-specific data.

Methods:

- `age(t) -> int`: returns the state age at simulation time `t`.
- `mark(flag) -> None`: records a lifecycle event such as `dropped` or
  `delivered`.
- `has_flag(flag) -> bool`: checks whether that lifecycle event has occurred.

### `BellPair(id, source_id, target_qpu_id, created_at, occupancy=1, fidelity=None, flags=None, metadata=None)`

Represents one communication resource used for teleportation. A Bell pair is
created by the network, stored by a QPU, and consumed when a magic state is
teleported.

Parameters:

- `id`: readable Bell-pair identifier.
- `source_id`: source endpoint, usually a memory ID.
- `target_qpu_id`: QPU that stores and consumes this Bell pair.
- `created_at`: time the Bell pair was created.
- `occupancy`: amount of QPU Bell-pair capacity consumed.
- `fidelity`: optional quality value for future richer models.
- `flags` and `metadata`: lifecycle and extension fields.

Methods are the same as for `MagicState`: `age(t)`, `mark(flag)`, and
`has_flag(flag)`.

### `IdGenerator(prefix)`

Creates deterministic readable IDs. Use this when a component creates many
tokens and needs stable names in snapshots and tests.

- `new() -> str`: returns the next ID using the configured prefix.

### Compatibility Objects

- `MagicStateToken(produced_at, fidelity=1.0, source="factory")`: older token
  wrapper that behaves like a `MagicState` while exposing old attributes such as
  `produced_at`, `source`, and `token_id`.
- `TokenBatch(tokens)`: immutable container used by older code.
- `ensure_tokens(tokens, minimum=0)`: validates a token sequence.

## `factory.py`

**Role:** magic-state production.

Factories create magic states. They are intentionally unaware of the rest of the
system. The simulator decides where produced states are stored.

### `BernoulliMagicStateFactory`

The main factory model. It is useful when production is stochastic and each time
step may produce zero, one, or several magic states.

Parameters:

- `id`: component ID used in maps, metadata, and generated state IDs.
- `attached_memory_id`: default memory where simulator should route output.
- `production_probability`: success probability for each production attempt.
- `output_occupancy`: occupancy assigned to each produced state.
- `output_fidelity`: optional fidelity assigned to each produced state.
- `max_output_per_step`: number of independent attempts per time step.

Methods:

- `step(t, rng) -> list[MagicState]`: performs production attempts at time `t`
  and returns newly created states.
- `update_params(**kwargs) -> None`: updates factory parameters and revalidates
  them. Use this for mid-run parameter changes.
- `snapshot() -> dict`: returns a serializable summary of the factory settings.

### `MagicStateFactory`

Compatibility factory from the older API. It deterministically produces
`production_rate` tokens every `period` time steps.

- `produce(time) -> tuple[MagicStateToken, ...]`: old-style production method.
- `step(t, rng=None) -> list[MagicStateToken]`: adapter method so it can be used
  by the new `Simulator`.

## `memory.py`

**Role:** storage, capacity enforcement, and memory decoherence.

Memory owns stored magic states. It enforces finite capacity, handles
decoherence, and provides states when the network needs to teleport them.

### `FiniteMemory`

Finite occupancy-based memory.

Supported construction patterns:

```python
FiniteMemory(50)
FiniteMemory("memory_0", 50)
FiniteMemory(id="memory_0", capacity=50)
```

Parameters:

- `id`: memory identifier used by factories, network edges, and routing maps.
- `capacity`: maximum total occupancy.
- `decoherence_probability`: probability that each stored state is removed in a
  call to `step(t, rng)`.
- `drop_policy`: policy used when adding a state would exceed capacity.
- `selection_policy`: policy used when popping states for teleportation.

Methods:

- `add(state, t=0, rng=None) -> bool`: planned single-state insertion. It may
  drop existing states to make room.
- `add_many(states, t, rng) -> list[MagicState]`: inserts several states and
  returns the states that were accepted.
- `pop_by_id(state_id) -> MagicState | None`: removes a specific state, useful
  for tests or explicit scheduling.
- `pop_available(n, t=0, policy=None) -> list[MagicState]`: removes up to `n`
  states selected by a policy. The default is oldest first.
- `list() -> list[MagicState]`: returns a copy of stored contents.
- `occupancy() -> int | float`: returns total used capacity.
- `step(t, rng) -> None`: applies decoherence and then enforces capacity.
- `enforce_capacity(t=0, rng=None) -> None`: drops stored states until capacity
  is respected. This is called after capacity shrink.
- `update_params(**kwargs) -> None`: strict parameter update helper.
- `snapshot() -> dict`: serializable memory summary.

Compatibility note: `add([token1, token2])` follows the old strict batch API and
raises `MemoryFullError` on overflow rather than applying planned drop policy.

## `policies.py`

**Role:** reusable decision logic.

Policies encapsulate decisions that should be easy to replace.

### Planned Drop Policies

- `DefaultDropPolicy`: general-purpose policy. It chooses lowest fidelity when
  fidelity exists, otherwise oldest, otherwise random.
- `DropLowestFidelityPolicy`: useful when fidelity should dominate retention.
- `DropOldestPolicy`: useful for FIFO-like memory behavior.
- `DropRandomPolicy`: useful for randomized baselines or fallback behavior.

All drop policies implement:

- `select(states, *, t, rng)`: returns one object to remove, or `None`.

### Planned Selection Policy

- `OldestFirstSelectionPolicy`: chooses oldest magic states when the network asks
  memory for states to teleport.

It implements:

- `select(states, n, *, t, rng) -> list[MagicState]`

### Compatibility Policies

These are preserved for older code:

- `DropNewestOnOverflow`: admits only what fits and drops incoming overflow.
- `DropOldestOnOverflow`: drops old memory contents to admit new incoming tokens.
- `RoundRobinRoutingPolicy`: cycles through destination choices.
- `RandomRoutingPolicy`: chooses destinations randomly.
- `ConsumptionPolicy`: stores old-style `tokens_per_operation`.

## `qpu.py`

**Role:** QPU-side communication resources and delivery accounting.

The QPU owns communication resources and records delivered magic states. It does
not own computation logic.

### `QPU`

Parameters:

- `id`: QPU identifier used by requests and network edges.
- `bell_pair_capacity`: maximum Bell-pair occupancy. Defaults to infinity.
- `bell_pair_decoherence_probability`: probability each Bell pair is removed in
  `step(t, rng)`.
- `bell_pair_drop_policy`: policy used if Bell-pair storage overflows.

Methods:

- `add_bell_pair(bell_pair, t=0, rng=None) -> bool`: asks the QPU to store a new
  Bell pair. May drop existing Bell pairs if needed.
- `consume_bell_pair(source_id=None) -> BellPair | None`: removes the oldest
  matching Bell pair for teleportation.
- `available_bell_pairs(source_id=None) -> int`: counts stored Bell pairs.
- `bell_pair_occupancy(source_id=None) -> int | float`: reports Bell-pair
  capacity usage.
- `receive_magic_state(state, t=0) -> None`: records successful magic-state
  delivery.
- `drain_received_magic_states() -> int`: clears and counts delivered states.
- `step(t, rng) -> None`: applies Bell-pair decoherence and capacity
  enforcement.
- `update_params(**kwargs) -> None`: strict parameter update helper.
- `snapshot() -> dict`: serializable QPU summary.

Compatibility methods:

- `receive(tokens)`: old-style magic-state buffer insertion.
- `can_execute(tokens_required=1)`: checks whether old-style buffered execution
  can run.
- `execute(tokens_required=1)`: consumes old-style buffered magic states.

## `network.py`

**Role:** Bell-pair creation, teleportation, and delayed delivery.

The network owns communication edges and delayed deliveries. It does not own
memory or QPU state; those are passed in by the simulator.

### `NetworkEdge`

Describes one directed communication route.

Parameters:

- `source_id`: source endpoint, usually a memory ID.
- `target_id`: destination endpoint, usually a QPU ID.
- `loss_probability`: shorthand for Bell-pair creation loss.
- `bell_pair_success_probability`: explicit probability of Bell-pair creation.
- `teleport_success_probability`: probability that a teleport attempt succeeds
  once resources exist.
- `latency`: delivery delay for successful teleportation.
- `communication_capacity`: reserved for future edge-level capacity handling.
- `metadata`: extension dictionary, for example Bell-pair fidelity.

If both `loss_probability` and `bell_pair_success_probability` are supplied,
they must agree.

### `LossyNetwork`

Main network implementation.

Methods:

- `add_edge(edge) -> None`: registers a directed communication route.
- `get_edge(source_id, target_id) -> NetworkEdge`: retrieves a route or raises a
  configuration error.
- `update_edge_params(source_id, target_id, **kwargs) -> None`: changes edge
  behavior for future attempts.
- `establish_bell_pairs(source_id, qpu, n, t, rng) -> list[BellPair]`: attempts
  to create `n` Bell pairs and store successful ones at the target QPU.
- `teleport(memory, qpu, n, t, rng) -> list[MagicState]`: attempts to teleport
  up to `n` states. It consumes one magic state and one Bell pair per attempt.
- `step(t, rng=None) -> list[tuple[str, MagicState]]`: releases delayed
  deliveries whose delivery time has arrived.
- `snapshot() -> dict`: serializable network state.

Compatibility methods:

- `send(token, destination, time) -> bool`: old direct token send without Bell
  pairs.
- `tick(time) -> tuple[MagicState, ...]`: old direct delivery tick.

## `computation.py`

**Role:** workload demand and progress tracking.

Computation models generate demand. They receive counts of delivered magic
states; they do not fetch states directly.

### `MagicStateRequest(qpu_id, n_states, request_id, priority=0, deadline=None, metadata=None)`

Represents active demand for magic states.

Fields:

- `qpu_id`: QPU where states are needed.
- `n_states`: number of states requested.
- `request_id`: stable identifier for the demand source.
- `priority`, `deadline`, `metadata`: hooks for future schedulers.

### `FixedPeriodicComputation`

Simple one-round-at-a-time workload.

Parameters:

- `qpu_id`: QPU where each round needs states.
- `interval`: number of time steps between rounds.
- `magic_states_per_round`: demand per round.
- `start_time`: first time a round can become active.
- `allow_failure`: whether excessive stalling can fail the computation.
- `failure_after_stall`: stall threshold if failure is enabled.

Compatibility aliases:

- `period` maps to `interval`.
- `tokens_per_operation` maps to `magic_states_per_round`.

Methods:

- `step(t, rng=None) -> None`: opens due rounds, counts stall time, and completes
  rounds after enough states arrive.
- `get_active_requests(t) -> list[MagicStateRequest]`: exposes current unmet
  demand.
- `receive_magic_states(qpu_id, n, t) -> None`: reduces active demand and
  records consumed or wasted states.
- `is_complete() -> bool`: currently always false for periodic workloads.
- `completed_work_count() -> int`: returns completed rounds.
- `throughput(t) -> float`: completed rounds per elapsed step.
- `snapshot() -> dict`: serializable computation state.

### `ComputationNode`

Node object for DAG workloads.

Fields describe:

- identity and QPU assignment;
- compute duration;
- required magic states;
- dependency IDs;
- runtime status and remaining work.

### `DAGComputation`

Dependency-constrained workload.

Methods:

- `ready_nodes()`: returns nodes whose dependencies are complete and which are
  not yet running or complete.
- `demand_at(time) -> int`: compatibility helper returning demand for the first
  ready node.
- `step(t, rng=None) -> None`: starts ready nodes on available QPUs, decrements
  compute time, and completes nodes when compute and magic demand are done.
- `get_active_requests(t) -> list[MagicStateRequest]`: exposes magic-state
  demand for running nodes.
- `receive_magic_states(qpu_id, n, t) -> None`: applies delivered states to the
  node currently running on that QPU.
- `is_complete() -> bool`: true when all nodes are complete.
- `snapshot() -> dict`: serializable DAG state.

## `simulator.py`

**Role:** central time-step orchestration.

The simulator coordinates all component interactions.

### `Simulator`

Parameters:

- `factories`: mapping from factory ID to factory object.
- `memories`: mapping from memory ID to memory object.
- `network`: network object.
- `qpus`: mapping from QPU ID to QPU object.
- `computation`: computation demand model.
- `factory_memory_map`: explicit factory-output routing.
- `qpu_memory_map`: static request routing from QPU to source memory.
- `seed`: RNG seed for reproducibility.
- `stats`: optional existing `SimulationStats` object.

Methods:

- `validate() -> None`: checks that all factory and QPU routes exist.
- `step() -> SimulationStats`: advances one time step using the central
  orchestration order.
- `run(num_steps) -> SimulationStats`: advances several time steps.
- `reset(seed=None) -> None`: resets time, RNG, and stats.
- `snapshot() -> dict`: serializable full-system state.
- `update_component_params(component_type, component_id, **kwargs) -> None`:
  strict runtime parameter update helper.

### `MagicStateSimulator`

Compatibility adapter for the original one-factory, one-memory simulator. It
builds a planned `Simulator` internally. New code should prefer constructing
`Simulator` directly.

## `stats.py`

**Role:** cumulative counters and per-step history.

Statistics are stored separately from model objects so the simulation can be
inspected without mixing accounting logic into each component.

### `SimulationStats`

Fields:

- `counters`: cumulative integer counters.
- `history`: list of per-step dictionaries.

Methods:

- `inc(key, amount=1)`: increments a counter.
- `record_step(t, simulator, delivered_by_qpu=None)`: captures one time-step
  summary.
- `as_dict() -> dict`: returns counters plus old compatibility key names.
- `to_dataframe()`: converts `history` to a pandas DataFrame. Pandas is imported
  only inside this method.
