# Distributed network simulation

A Python framework for synchronous distributed algorithms in the CONGEST and
sleeping CONGEST models. The reusable simulator is in `src/dn_simulation`; the
algorithms are implemented separately in `examples` using its public node API.

## Install and run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands from the repository root. `uv sync` uses `.python-version` to
install Python 3.13 if needed, creates `.venv`, and installs the project and its
development dependencies from `uv.lock`.

```sh
uv sync --locked
uv run --locked python -m examples.broadcast
uv run --locked python -m examples.bfs_max
uv run --locked python -m examples.leader_election
uv run --locked python -m examples.mst
uv run --locked python -m examples.sleeping_broadcast
uv run --locked pytest
```

Run `uv sync --locked --extra visualization` to install Matplotlib for the
optional `draw_graph` helper, and use `uv run --locked --extra visualization`
when running code that calls it. Use `uv add`, `uv add --dev`, or
`uv add --optional visualization` to change dependencies; uv updates
`pyproject.toml`, `uv.lock`, and the environment together.

The simulator gives a node its ID, neighbors and incident binary64 edge weights.
It cannot inspect the entire topology through the node interface. Messages sent
in round `r` arrive at the start of `r + 1`. A directed link carries at most
one message per round. Each message is encoded by the example's `SchemaCodec`
and must fit within `128 * ceil(log2(max(2, n)))` bits. The constant accommodates
fixed-size binary64 weights; the limit remains proportional to `log n`.
`AlgorithmNode.queue` maintains a FIFO per neighbor and transmits one queued
message per round. `Context.send` rejects a second direct send on the same link
in one round.

The framework accepts simple undirected NetworkX graphs with nonnegative integer
node IDs and finite edge weights. Integer weights must be exactly representable
as binary64. Very large node IDs can exceed the message budget when encoded.
An algorithm may require a connected graph; each example documents
its own assumptions. `Simulation.run()` stops when every node declares a result
or returns `completed=False` at the configured round limit. Its result includes
round, transmission, dropped-message and per-node awake-round counts.

`Model.CONGEST` keeps all unfinished nodes awake. In
`Model.SLEEPING_CONGEST`, a node can call `sleep_for(k)` to skip the next `k`
rounds. It wakes by its own timer. Messages arriving while it sleeps are lost;
no message can wake it. The migrated algorithms use standard CONGEST;
`sleeping_broadcast` illustrates self scheduled sleep. See
[the examples guide](examples/README.md) for their behavior and assumptions.

The original MST notebook is on the historical `ghs-mst-algorithm` branch.
