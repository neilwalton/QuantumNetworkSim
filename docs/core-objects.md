# Core Objects

This page explains the main objects in the package in terms of their role in a
simulation. The package is built around a central idea: each object owns one
piece of state or behavior, and the `Simulator` coordinates them in a fixed time
step order.

## Tokens

Tokens are lightweight records that move through the simulation. They do not
make decisions. They only carry identity, physical metadata, and lifecycle
flags.

### `MagicState`

`MagicState` represents one produced magic state. It is created by a factory,
stored in a memory, possibly teleported through the network, and eventually
delivered to computation.

The class is deliberately small. It stores the information that other
components need in order to make decisions:

- `id` is a readable unique name, such as `factory_0_state_1`.
- `created_at` records the simulation time when the state was made.
- `occupancy` is how much memory capacity this state consumes. In the current
  simple model it is usually `1`, but it may be a float for richer models.
- `fidelity` is optional. If present, drop policies can prefer to keep
  higher-fidelity states.
- `flags` records lifecycle events. For example, memory marks states as
  `in_memory`, failed teleportation marks states as `teleport_failed` and
  `destroyed`, and successful delivery marks states as `delivered`.
- `metadata` is a free-form extension dictionary. It lets later external
  simulators attach extra information without changing the class definition.

Important methods:

- `age(t)` returns `t - created_at`. It is used when policies need age-aware
  behavior.
- `mark(flag)` records that something happened to the state.
- `has_flag(flag)` checks whether a lifecycle event has occurred.

### `BellPair`

`BellPair` represents a communication resource between a source memory and a
target QPU. It is created by the network and stored at the QPU until used for
teleportation or removed by decoherence.

Its role is different from a `MagicState`: a Bell pair is not useful work for
the computation, but it is required to move magic states from memory to a QPU.
Teleporting one magic state consumes exactly one Bell pair.

Important fields:

- `source_id` identifies the memory or source endpoint the Bell pair connects
  from.
- `target_qpu_id` identifies the QPU that stores and consumes the Bell pair.
- `created_at`, `occupancy`, `fidelity`, `flags`, and `metadata` have the same
  general meaning as on `MagicState`.

The same helper methods are available: `age(t)`, `mark(flag)`, and
`has_flag(flag)`.

### `IdGenerator`

`IdGenerator` creates stable readable identifiers. It avoids relying on Python
object IDs, which are not meaningful across runs. A generator with prefix
`state` produces IDs like `state_1`, `state_2`, and `state_3`.

Factories own magic-state ID generators. The network owns a Bell-pair ID
generator.

## Factories

Factories are the source of magic states. A factory does not know about memory,
networks, QPUs, or computation. Its only task is to produce zero or more
`MagicState` objects when asked by the simulator.

### `BernoulliMagicStateFactory`

`BernoulliMagicStateFactory` is the main planned factory model. At each time
step it performs `max_output_per_step` independent production attempts. Each
attempt succeeds with probability `production_probability`.

For example, with `production_probability=1.0` and `max_output_per_step=3`,
the factory always returns three states per time step. With
`production_probability=0.0`, it never returns any states.

The factory also assigns:

- `output_occupancy` to each produced state;
- `output_fidelity` to each produced state if provided;
- metadata recording the factory ID.

The factory has an `attached_memory_id`, but it does not insert states into that
memory. The simulator reads this field, or the explicit `factory_memory_map`,
and performs insertion centrally.

### `MagicStateFactory` Compatibility Wrapper

`MagicStateFactory` is the older deterministic periodic factory. It remains for
compatibility with earlier examples. It produces `MagicStateToken` objects every
`period` time steps. New code should normally use `BernoulliMagicStateFactory`.

## Memory

Memory stores produced magic states until computation requests cause the network
to teleport them to a QPU.

### `FiniteMemory`

`FiniteMemory` is an occupancy-limited memory. Capacity is not the number of
states; it is the sum of `state.occupancy` for all stored states. This matters
because later models may have states that occupy fractional or multiple memory
units.

The memory has three main jobs:

1. Accept produced states if capacity can be respected.
2. Drop existing states according to a policy when capacity would overflow.
3. Remove states that decohere during a simulation step.

When adding a new state, the planned behavior is:

1. Reject the state if it is larger than the whole memory.
2. If the memory would overflow, repeatedly select old contents to drop.
3. Insert the new state if enough room can be made.
4. Mark accepted states as `in_memory`.

The default drop policy is intentionally simple and physically interpretable:

1. Drop the lowest-fidelity state if any stored states have fidelity.
2. Otherwise drop the oldest state.
3. If neither concept is available, drop randomly.

Important methods:

- `add(state, t, rng)` inserts one state and returns whether it was accepted.
- `add_many(states, t, rng)` inserts several states and returns the accepted
  subset.
- `pop_by_id(state_id)` removes one specific state.
- `pop_available(n, t)` removes up to `n` states selected by the memory's
  selection policy. The default is oldest first.
- `step(t, rng)` applies binary decoherence and then enforces capacity.
- `enforce_capacity(t, rng)` is also used after capacity changes.
- `snapshot()` returns a serializable summary for inspection or logging.

The class also supports the old constructor style `FiniteMemory(8)` and the
planned style `FiniteMemory("memory_0", 8)` or
`FiniteMemory(id="memory_0", capacity=8)`.

## Policies

Policies isolate small decisions that may need to be changed later. This lets
the memory, QPU, and simulator keep simple logic while still supporting different
selection strategies.

### Drop Policies

Drop policies choose which object should be removed when capacity is exceeded.
They are used by `FiniteMemory` and by QPU Bell-pair storage.

- `DefaultDropPolicy` chooses lowest fidelity, then oldest, then random.
- `DropLowestFidelityPolicy` drops the object with the smallest non-`None`
  fidelity.
- `DropOldestPolicy` drops the object with the earliest `created_at`.
- `DropRandomPolicy` drops a random object from the candidates.

### Selection Policies

Selection policies choose which magic states leave memory for teleportation.

- `OldestFirstSelectionPolicy` is the current default. It prefers states that
  have waited longest in memory.

### Compatibility Policies

The original package included simple storage and routing policies. They remain
for older code:

- `DropNewestOnOverflow`
- `DropOldestOnOverflow`
- `RoundRobinRoutingPolicy`
- `RandomRoutingPolicy`
- `ConsumptionPolicy`

These are mainly used by compatibility wrappers, not by the planned central
simulator flow.

## QPU

The QPU represents a target endpoint for computation. In the planned API, its
main physical resource is Bell-pair communication memory.

### `QPU`

`QPU` stores Bell pairs that have been established by the network. It does not
own the computation object and does not decide how many magic states are needed.
The simulator coordinates that interaction.

The QPU's responsibilities are:

1. Accept Bell pairs if communication capacity allows.
2. Drop Bell pairs according to a policy if capacity would overflow.
3. Consume Bell pairs during teleportation.
4. Remove decohered Bell pairs during `step(t, rng)`.
5. Record delivered magic states so that the simulator can pass counts to
   computation.

Important methods:

- `add_bell_pair(bell_pair, t, rng)` stores one Bell pair if possible.
- `consume_bell_pair(source_id=None)` removes and returns the oldest matching
  Bell pair.
- `available_bell_pairs(source_id=None)` counts stored Bell pairs, optionally
  filtered by source memory.
- `bell_pair_occupancy(source_id=None)` returns total Bell-pair occupancy.
- `receive_magic_state(state, t)` records successful delivery.
- `step(t, rng)` applies Bell-pair decoherence.

The QPU still has compatibility methods `receive()` and `execute()` from the
older model where QPUs directly buffered magic states. New simulator code should
not rely on those methods.

## Network

The network mediates communication. It does not own magic-state memory and it
does not own QPU state. Instead, it is given memories and QPUs by the simulator
when work needs to be served.

### `NetworkEdge`

`NetworkEdge` describes one directed route, usually from a memory to a QPU.
It is the place where communication parameters live.

Important fields:

- `source_id` and `target_id` define the route.
- `bell_pair_success_probability` controls whether Bell-pair creation succeeds.
- `teleport_success_probability` controls whether a teleport attempt succeeds
  once both resources exist.
- `latency` delays successful delivery by a number of time steps.
- `metadata` can store extra edge data such as Bell-pair fidelity.

`loss_probability` is accepted as shorthand for Bell-pair creation loss. If
used alone, it means:

```python
bell_pair_success_probability = 1.0 - loss_probability
```

### `LossyNetwork`

`LossyNetwork` owns the graph of `NetworkEdge` objects and the in-flight delivery
queue for positive-latency teleportation.

Its planned responsibilities are:

1. Store configured directed edges.
2. Create Bell pairs and ask target QPUs to store them.
3. Teleport magic states from memories to QPUs.
4. Destroy states on failed teleportation.
5. Release delayed deliveries when their delivery time arrives.

Teleportation is deliberately conservative. Before consuming anything, the
network checks that both resources exist:

- at least one magic state in the source memory;
- at least one Bell pair at the target QPU for that source memory.

If teleportation succeeds with `latency=0`, the state is returned immediately.
If latency is positive, the state is stored in the network's in-flight queue and
released by `network.step(t, rng)` at the correct time.

The old direct-send API, `send()` and `tick()`, remains only for compatibility.
It bypasses Bell pairs and should not be used in new simulator code.

## Computation

Computation models represent demand for magic states. They do not pull directly
from memory or QPUs. Instead, they expose requests, and the simulator tries to
serve those requests through memory and network resources.

### `MagicStateRequest`

`MagicStateRequest` is the data structure computation returns to the simulator.
It says:

- which QPU needs states;
- how many states are needed;
- which request or round the demand belongs to;
- optional priority, deadline, and metadata.

The current simulator uses static QPU-to-memory routing. More advanced
schedulers can use the request metadata later.

### `FixedPeriodicComputation`

`FixedPeriodicComputation` is the simplest demand model. It opens one active
round at a time. Every `interval` time steps, a round becomes due and requires
`magic_states_per_round` delivered states at a fixed QPU.

If states are not delivered, the computation stalls. Stall time is counted once
per simulation time step even though the simulator may call `step()` twice at
the same time: once before requests and once after deliveries.

When enough states arrive, the active round completes and the next round is
scheduled for a future time step.

The class tracks:

- `completed_rounds`
- `remaining_magic_states`
- `stall_time`
- `total_magic_states_consumed`
- `wasted_magic_states`
- optional failure state if `allow_failure=True`

### `ComputationNode`

`ComputationNode` is the unit of work in `DAGComputation`. It records a node ID,
assigned QPU, compute time, magic-state requirement, dependencies, and runtime
state such as remaining compute time and remaining magic-state demand.

### `DAGComputation`

`DAGComputation` models dependency-constrained computation. Nodes become ready
only after their dependencies complete. A node completes only when:

1. its compute time has elapsed; and
2. all required magic states have been received.

The current implementation is intentionally modest:

- cyclic DAGs are rejected at construction;
- each QPU runs at most one node at a time;
- scheduling is first-ready, first-started;
- richer scheduling policies can be added later.

## Simulator

The `Simulator` is the central coordinator. It owns the dictionaries of
factories, memories, QPUs, the network, the computation model, the random number
generator, and the statistics object.

Its role is to keep components decoupled. For example:

- factories never call memories;
- memories never call the network;
- the network never calls computation;
- QPUs never decide what computation needs.

Instead, `Simulator.step()` performs the full time step in a known order. This
ordering is the most important part of the package because it defines the
meaning of all counters and lifecycle flags.

Important methods:

- `validate()` checks that factories, memories, QPUs, and network edges are
  consistently connected.
- `step()` advances exactly one simulation time step.
- `run(num_steps)` repeatedly calls `step()`.
- `reset(seed=None)` resets time, RNG, and stats.
- `snapshot()` returns a nested serializable state summary.
- `update_component_params(...)` changes component settings during a run.

## Statistics

### `SimulationStats`

`SimulationStats` records both cumulative counters and per-step history.

The cumulative `counters` dictionary is useful for totals such as:

- states created;
- states accepted by memory;
- Bell pairs attempted and created;
- teleport attempts, successes, and failures;
- states delivered;
- completed operations.

The `history` list stores one dictionary per time step. It is intended for plots
and debugging. It includes memory occupancy, memory counts, QPU Bell-pair
counts, active requests, delivered states per QPU, completed work, and
throughput.

`as_dict()` returns a compatibility-friendly flat dictionary. `to_dataframe()`
imports pandas only when called, so pandas is not required for core simulation.
