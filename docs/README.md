# Magic State Simulator Documentation

This folder documents the main package concepts, objects, and workflows.

## Contents

- [Architecture](architecture.md): how the simulator is structured and how a time step runs.
- [Core Objects](core-objects.md): tokens, factories, memories, QPUs, networks, computation, and stats.
- [Public API Reference](api-reference.md): key classes, methods, and compatibility wrappers.
- [Examples](examples.md): common setup patterns and usage snippets.

The package code lives in `magic_state_sim/`. New projects should prefer the planned API:

```python
from magic_state_sim import (
    BernoulliMagicStateFactory,
    FiniteMemory,
    LossyNetwork,
    NetworkEdge,
    QPU,
    FixedPeriodicComputation,
    Simulator,
)
```

The original smaller API remains available through compatibility wrappers such as
`MagicStateFactory`, `MagicStateSimulator`, and `MagicStateToken`.
