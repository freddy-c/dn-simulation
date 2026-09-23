# Algorithm examples

Each `.py` file here implements node behavior using `dn_simulation.AlgorithmNode`
and supplies its own compact message schema. Run them from the repository root
with `uv run --locked python -m examples.<name>`. The simulator package contains no
algorithm-specific protocol.

| Example | Output | Input assumptions |
| --- | --- | --- |
| `broadcast` | Each node learns its neighbors' IDs or their largest incident edge weight | Any nonempty simple undirected graph |
| `leader_election` | Every node reports the minimum node ID | Connected graph |
| `bfs_max` | Each node reports its BFS parent, hop distance, children and network maximum | Connected graph, source ID and finite values for all nodes |
| `mst` | Every node reports its selected tree neighbors | Connected graph with finite binary64 weights, including negative, zero and ties |
| `sleeping_broadcast` | Each node learns its neighbors' IDs after choosing its own wake round | Any nonempty simple undirected graph; sleeping CONGEST |

The leader election example runs a flood and echo wave from every node, then
floods the first completed result. It has a simple local termination condition
but is intentionally message-heavy. The MST example preserves the historical
mutual fragment-merge design. A new fragment waits for an acknowledgment from
its whole branch tree before searching again. Edge ties use the ordered key
`(weight, lower endpoint ID, higher endpoint ID)`.

For MST, `mst.edges(result)` collects the undirected edge set after all nodes
complete. This is postprocessing for display and tests; nodes do not receive a
global edge set from the simulator. The migrated algorithms use standard
CONGEST. `sleeping_broadcast` shows the separate sleeping model API.
