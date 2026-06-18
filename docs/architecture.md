# Architecture

`magic_state_sim` is a discrete-time simulator for magic-state production,
storage, Bell-pair-mediated teleportation, QPU delivery, and computation demand.

The intended structure is:

```text
Factory -> Memory -> Network -> QPU -> Computation
```

The components do not directly drive each other. A central `Simulator` owns the
time loop and coordinates all interactions. This keeps each component small and
replaceable.

## Package Layout

```text
magic_state_sim/
    tokens.py        # MagicState, BellPair, ID generation, validation
    factory.py       # magic-state factory models
    memory.py        # finite occupancy-based magic-state memory
    policies.py      # drop, selection, storage, and routing policies
    network.py       # network edges, Bell-pair creation, teleportation
    qpu.py           # QPU Bell-pair memory and receive/execute compatibility API
    computation.py   # fixed-periodic and DAG computation demand models
    simulator.py     # central Simulator and compatibility MagicStateSimulator
    stats.py         # cumulative counters and per-step history
    config.py        # simple configuration dataclass
    exceptions.py    # package-specific exceptions
```

## Time Step Order

For each call to `Simulator.step()`, the central coordinator uses this order:

1. Memories age/decohere stored magic states.
2. QPUs age/decohere stored Bell pairs.
3. Computation updates active work and exposes demand.
4. Factories produce magic states.
5. Produced states are inserted into their attached memories.
6. Computation requests are routed to source memories.
7. The network establishes missing Bell pairs.
8. The network teleports magic states using one Bell pair per state.
9. Delayed in-flight deliveries are released.
10. Delivered magic states are passed to the computation.
11. Statistics are recorded.
12. Simulation time increments.

States produced at time `t` may be used at time `t`. This is a simple discrete
time convention and can be changed later by adding factory latency.

## Main Design Rules

- Factories return produced states; they do not insert into memory directly.
- Memories store magic states and enforce occupancy capacity.
- QPUs store Bell pairs, not long-lived magic-state buffers in the planned API.
- The network creates Bell pairs and teleports magic states, but it does not own QPUs.
- Computation owns demand and receives delivered magic-state counts.
- Statistics are collected centrally by the simulator.

## Compatibility Layer

The package also preserves the original small FIFO-token API:

- `MagicStateToken`
- `MagicStateFactory`
- `MagicStateSimulator`
- `QPU.receive()` and `QPU.execute()`
- `LossyNetwork.send()` and `LossyNetwork.tick()`

These wrappers are intended for older examples and tests. New code should use
`MagicState`, `BernoulliMagicStateFactory`, `NetworkEdge`, and `Simulator`.
