"""One-round neighbor ID and local maximum broadcasts."""
from dn_simulation import AlgorithmNode, SchemaCodec, Simulation

ID_CODEC = SchemaCodec({"id": ("id",)})
MAX_CODEC = SchemaCodec({"max": ("bool", "weight")})


class NeighborIDs(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if ctx.round == 0:
            for neighbor in self.neighbors:
                self.queue(neighbor, "id", self.node_id)
        if ctx.round >= 1 or not self.neighbors:
            ctx.finish({sender: packet.values[0] for sender, packet in inbox})


class NeighborMaxWeight(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if ctx.round == 0:
            maximum = max(self.neighbors.values(), default=None)
            for neighbor in self.neighbors:
                self.queue(neighbor, "max", maximum is not None, maximum if maximum is not None else 0.0)
        if ctx.round >= 1 or not self.neighbors:
            ctx.finish({sender: value if present else None for sender, packet in inbox for present, value in [packet.values]})


def neighbor_ids(graph):
    return Simulation(graph, NeighborIDs, ID_CODEC).run()


def neighbor_max_weights(graph):
    return Simulation(graph, NeighborMaxWeight, MAX_CODEC).run()


if __name__ == "__main__":
    import networkx as nx

    graph = nx.Graph()
    graph.add_weighted_edges_from([(0, 1, 2), (1, 2, -3), (0, 2, 4)])
    print("IDs:", neighbor_ids(graph).node_results)
    print("Neighbor maxima:", neighbor_max_weights(graph).node_results)
