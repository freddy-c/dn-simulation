"""A synchronous, local-view CONGEST simulator."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import math
import struct
from typing import Callable, Mapping

import networkx as nx


class Model(str, Enum):
    CONGEST = "congest"
    SLEEPING_CONGEST = "sleeping_congest"


@dataclass(frozen=True)
class Packet:
    kind: str
    values: tuple = ()


class SchemaCodec:
    """Bit-pack fixed schemas. Fields are id, epoch, weight or bool."""

    def __init__(self, schemas: Mapping[str, tuple[str, ...]]):
        if not schemas:
            raise ValueError("at least one message kind is required")
        self.schemas = dict(schemas)
        self.tags = {kind: i for i, kind in enumerate(schemas)}
        self.kinds = list(schemas)

    def _width(self, field: str, id_sentinel: int, round_limit: int) -> int:
        if field == "id":
            return max(1, id_sentinel.bit_length())
        if field == "epoch":
            return max(1, round_limit.bit_length())
        if field == "weight":
            return 64
        if field == "bool":
            return 1
        raise ValueError(f"unknown field type: {field}")

    def encode(self, packet: Packet, id_sentinel: int, round_limit: int) -> bytes:
        if packet.kind not in self.schemas:
            raise ValueError(f"unknown message kind: {packet.kind}")
        fields = self.schemas[packet.kind]
        if len(fields) != len(packet.values):
            raise ValueError(f"{packet.kind} expects {len(fields)} values")
        width = max(1, (len(self.schemas) - 1).bit_length())
        bits = self.tags[packet.kind]
        for field, value in zip(fields, packet.values):
            size = self._width(field, id_sentinel, round_limit)
            if field == "weight":
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError("weights must be finite")
                value = int.from_bytes(struct.pack(">d", value), "big")
            elif field == "id":
                value = id_sentinel if value is None else value
                if not isinstance(value, int) or not 0 <= value <= id_sentinel:
                    raise ValueError("invalid node ID")
            elif field == "epoch":
                if not isinstance(value, int) or not 0 <= value <= round_limit:
                    raise ValueError("epoch exceeds configured round limit")
            elif field == "bool":
                value = int(bool(value))
            bits = (bits << size) | value
            width += size
        padding = -width % 8
        return (bits << padding).to_bytes((width + 7) // 8, "big")

    def decode(self, data: bytes, id_sentinel: int, round_limit: int) -> Packet:
        tag_bits = max(1, (len(self.schemas) - 1).bit_length())
        for kind, fields in self.schemas.items():
            widths = [self._width(f, id_sentinel, round_limit) for f in fields]
            total = tag_bits + sum(widths)
            if len(data) != (total + 7) // 8:
                continue
            bits = int.from_bytes(data, "big") >> (-total % 8)
            if bits >> sum(widths) != self.tags[kind]:
                continue
            values = []
            remaining = sum(widths)
            for field, size in zip(fields, widths):
                remaining -= size
                value = (bits >> remaining) & ((1 << size) - 1)
                if field == "weight":
                    value = struct.unpack(">d", value.to_bytes(8, "big"))[0]
                elif field == "id" and value == id_sentinel:
                    value = None
                elif field == "bool":
                    value = bool(value)
                values.append(value)
            return Packet(kind, tuple(values))
        raise ValueError("invalid encoded packet")


class AlgorithmNode:
    """Subclass in an example; keep algorithm state here, not in the simulator."""

    def __init__(self, node_id: int, neighbors: Mapping[int, float]):
        self.node_id = node_id
        self.neighbors = dict(neighbors)
        self._outbound: dict[int, deque[Packet]] = defaultdict(deque)
        self.done = False
        self.result = None
        self.wake_round = 0

    def queue(self, neighbor: int, kind: str, *values) -> None:
        if self.done:
            raise ValueError("completed node cannot send")
        if neighbor not in self.neighbors:
            raise ValueError(f"{neighbor} is not a neighbor of {self.node_id}")
        self._outbound[neighbor].append(Packet(kind, values))

    def on_round(self, ctx: "Context", inbox: list[tuple[int, Packet]]) -> None:
        raise NotImplementedError


class Context:
    def __init__(self, simulation: "Simulation", node: AlgorithmNode):
        self._simulation = simulation
        self._node = node
        self.round = simulation.round
        self._sent_to: set[int] = set()

    def send(self, neighbor: int, packet: Packet) -> None:
        if neighbor not in self._node.neighbors:
            raise ValueError(f"{neighbor} is not a neighbor of {self._node.node_id}")
        if neighbor in self._sent_to:
            raise ValueError(f"at most one message to {neighbor} may be sent in a round")
        encoded = self._simulation.codec.encode(packet, self._simulation.id_sentinel, self._simulation.round_limit)
        if len(encoded) * 8 > self._simulation.message_bits:
            raise ValueError(f"message exceeds CONGEST limit on {self._node.node_id}->{neighbor}")
        self._sent_to.add(neighbor)
        self._simulation._inflight.append((self._node.node_id, neighbor, encoded))
        self._simulation.sent_messages += 1

    def sleep_for(self, rounds: int) -> None:
        if self._simulation.model != Model.SLEEPING_CONGEST:
            raise ValueError("sleep requires the sleeping CONGEST model")
        if not isinstance(rounds, int) or rounds < 1:
            raise ValueError("sleep duration must be a positive integer")
        self._node.wake_round = self.round + rounds + 1

    def finish(self, result) -> None:
        self._node.result = result
        self._node.done = True


@dataclass(frozen=True)
class RunResult:
    completed: bool
    rounds: int
    sent_messages: int
    dropped_messages: int
    awake_rounds: dict[int, int]
    node_results: dict[int, object]


class Simulation:
    def __init__(
        self,
        graph: nx.Graph,
        node_factory: Callable[[int, Mapping[int, float]], AlgorithmNode],
        codec: SchemaCodec,
        *,
        model: Model = Model.CONGEST,
        round_limit: int = 5000,
    ):
        if not isinstance(graph, nx.Graph) or graph.is_multigraph() or graph.is_directed():
            raise ValueError("a simple undirected NetworkX graph is required")
        n = len(graph)
        if n == 0 or any(not isinstance(i, int) or i < 0 for i in graph.nodes):
            raise ValueError("node IDs must be nonnegative integers")
        if not isinstance(round_limit, int) or round_limit < 1:
            raise ValueError("round_limit must be positive")
        self.graph = graph.copy()
        self.id_sentinel = max(self.graph.nodes) + 1
        for _, _, data in self.graph.edges(data=True):
            weight = data.get("weight", 1.0)
            if isinstance(weight, int) and float(weight) != weight:
                raise ValueError("integer weight loses precision in binary64")
            weight = float(weight)
            if not math.isfinite(weight):
                raise ValueError("edge weights must be finite")
            data["weight"] = weight
        self.nodes = {
            i: node_factory(i, {j: self.graph.edges[i, j]["weight"] for j in self.graph.neighbors(i)})
            for i in sorted(self.graph.nodes)
        }
        if any(node.node_id != i for i, node in self.nodes.items()):
            raise ValueError("node factory returned a mismatched node ID")
        self.codec = codec
        self.model = Model(model)
        self.round_limit = round_limit
        self.round = 0
        self._inflight: list[tuple[int, int, bytes]] = []
        self.sent_messages = 0
        self.dropped_messages = 0
        self.awake_rounds = {i: 0 for i in self.nodes}
        self.message_bits = 128 * max(1, math.ceil(math.log2(max(2, n))))

    def step(self) -> RunResult:
        if self.round >= self.round_limit:
            raise RuntimeError("round limit reached")
        if all(node.done for node in self.nodes.values()):
            return self.snapshot()
        inbox: dict[int, list[tuple[int, Packet]]] = defaultdict(list)
        for sender, receiver, data in self._inflight:
            node = self.nodes[receiver]
            if node.done or node.wake_round > self.round:
                self.dropped_messages += 1
            else:
                inbox[receiver].append((sender, self.codec.decode(data, self.id_sentinel, self.round_limit)))
        self._inflight = []
        for node_id, node in self.nodes.items():
            if node.done or node.wake_round > self.round:
                continue
            self.awake_rounds[node_id] += 1
            ctx = Context(self, node)
            node.on_round(ctx, inbox[node_id])
            for neighbor, pending in list(node._outbound.items()):
                if not pending:
                    continue
                packet = pending.popleft()
                ctx.send(neighbor, packet)
            if node.wake_round > self.round + 1 and any(node._outbound.values()):
                raise ValueError("node cannot sleep with queued messages")
        self.round += 1
        return self.snapshot()

    def snapshot(self) -> RunResult:
        return RunResult(
            completed=all(node.done for node in self.nodes.values()),
            rounds=self.round,
            sent_messages=self.sent_messages,
            dropped_messages=self.dropped_messages,
            awake_rounds=self.awake_rounds.copy(),
            node_results={i: node.result for i, node in self.nodes.items()},
        )

    def run(self) -> RunResult:
        while self.round < self.round_limit and not all(node.done for node in self.nodes.values()):
            self.step()
        return self.snapshot()
