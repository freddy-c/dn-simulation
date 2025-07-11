"""A small demonstration of self scheduled sleep in sleeping CONGEST.

Every node independently sleeps through rounds 1 and 2, wakes in round 3,
and exchanges IDs. No incoming message wakes a sleeping node.
"""
from dn_simulation import AlgorithmNode, Model, SchemaCodec, Simulation

CODEC = SchemaCodec({"id": ("id",)})


class SleepingNeighborIDs(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if ctx.round == 0:
            ctx.sleep_for(2)
        elif ctx.round == 3:
            for neighbor in self.neighbors:
                self.queue(neighbor, "id", self.node_id)
        elif ctx.round == 4:
            ctx.finish({sender: packet.values[0] for sender, packet in inbox})


def run(graph):
    return Simulation(graph, SleepingNeighborIDs, CODEC, model=Model.SLEEPING_CONGEST).run()


if __name__ == "__main__":
    import networkx as nx

    print(run(nx.path_graph(4)))
