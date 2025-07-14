"""BFS tree construction followed by maximum-value convergecast."""
from dn_simulation import AlgorithmNode, SchemaCodec, Simulation
import networkx as nx

CODEC = SchemaCodec({
    "explore": (),
    "reject": (),
    "echo": ("weight",),
    "result": ("weight",),
})


class BFSMaxNode(AlgorithmNode):
    def __init__(self, node_id, neighbors, *, source, values):
        super().__init__(node_id, neighbors)
        self.source = source
        self.value = values[node_id]
        self.parent = None
        self.distance = 0 if node_id == source else None
        self.pending = set()
        self.children = set()
        self.subtree_max = self.value
        self.sent_echo = False
        self.result_started = False
        self.received_result = None

    def on_round(self, ctx, inbox):
        if ctx.round == 0 and self.node_id == self.source:
            self.pending = set(self.neighbors)
            for neighbor in self.neighbors:
                self.queue(neighbor, "explore")
        # All explorations from the same BFS layer arrive together. Break ties
        # by the sender's ID, independent of graph insertion order.
        offers = sorted(sender for sender, packet in inbox if packet.kind == "explore")
        if self.distance is None and offers:
            self.parent = offers[0]
            self.distance = ctx.round
            self.pending = set(self.neighbors) - {self.parent}
            for neighbor in self.pending:
                self.queue(neighbor, "explore")
        for sender, packet in inbox:
            if packet.kind == "explore":
                if sender != self.parent or (self.node_id == self.source):
                    self.queue(sender, "reject")
            elif packet.kind == "reject":
                self.pending.discard(sender)
            elif packet.kind == "echo":
                self.pending.discard(sender)
                self.children.add(sender)
                self.subtree_max = max(self.subtree_max, packet.values[0])
            elif packet.kind == "result":
                self.received_result = packet.values[0]
        if self.distance is not None and not self.pending and not self.sent_echo:
            self.sent_echo = True
            if self.parent is not None:
                self.queue(self.parent, "echo", self.subtree_max)
            else:
                self.received_result = self.subtree_max
        if self.received_result is not None and not self.result_started:
            self.result_started = True
            for child in self.children:
                self.queue(child, "result", self.received_result)
            ctx.finish({"parent": self.parent, "distance": self.distance, "children": tuple(sorted(self.children)), "maximum": self.received_result})


def run(graph, *, source: int, values: dict[int, float], round_limit=5000):
    if not graph or not nx.is_connected(graph):
        raise ValueError("BFS example requires a connected graph")
    if source not in graph or set(values) != set(graph):
        raise ValueError("source and values must cover the graph")
    import math
    if not all(math.isfinite(float(value)) for value in values.values()):
        raise ValueError("values must be finite")
    return Simulation(graph, lambda i, n: BFSMaxNode(i, n, source=source, values=values), CODEC, round_limit=round_limit).run()


if __name__ == "__main__":
    import networkx as nx

    graph = nx.cycle_graph(6)
    print(run(graph, source=0, values={i: i for i in graph}))
