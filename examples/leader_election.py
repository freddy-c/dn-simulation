"""Minimum-ID leader election without knowledge of network size.

Every node starts a flood/echo wave. The first completed wave has visited the
whole connected graph, so its echo contains the true minimum ID. It then floods
that decision. This favors a simple termination argument over message economy.
"""
from dataclasses import dataclass
import networkx as nx
from dn_simulation import AlgorithmNode, SchemaCodec, Simulation

CODEC = SchemaCodec({
    "explore": ("id",),
    "reply": ("id", "bool", "id"),
    "decide": ("id",),
})


@dataclass
class Wave:
    parent: int | None
    pending: set[int]
    minimum: int
    reported: bool = False


class LeaderElectionNode(AlgorithmNode):
    def __init__(self, node_id, neighbors):
        super().__init__(node_id, neighbors)
        self.waves: dict[int, Wave] = {}

    def decide(self, leader, incoming, ctx):
        # Priority over obsolete wave traffic. Every node forwards the decision
        # before halting, so other in-flight waves can be discarded safely.
        self._outbound.clear()
        for neighbor in self.neighbors:
            if neighbor != incoming:
                self.queue(neighbor, "decide", leader)
        ctx.finish(leader)

    def on_round(self, ctx, inbox):
        decisions = [(sender, packet.values[0]) for sender, packet in inbox if packet.kind == "decide"]
        if decisions:
            self.decide(decisions[0][1], decisions[0][0], ctx)
            return
        if ctx.round == 0:
            self.waves[self.node_id] = Wave(None, set(self.neighbors), self.node_id)
            for neighbor in self.neighbors:
                self.queue(neighbor, "explore", self.node_id)
        for sender, packet in inbox:
            if packet.kind == "explore":
                origin = packet.values[0]
                if origin in self.waves:
                    self.queue(sender, "reply", origin, False, self.node_id)
                else:
                    pending = set(self.neighbors) - {sender}
                    self.waves[origin] = Wave(sender, pending, self.node_id)
                    for neighbor in pending:
                        self.queue(neighbor, "explore", origin)
            elif packet.kind == "reply":
                origin, accepted, minimum = packet.values
                wave = self.waves[origin]
                wave.pending.discard(sender)
                if accepted:
                    wave.minimum = min(wave.minimum, minimum)
        for origin, wave in list(self.waves.items()):
            if wave.pending or wave.reported:
                continue
            wave.reported = True
            if wave.parent is None:
                self.decide(wave.minimum, None, ctx)
                return
            self.queue(wave.parent, "reply", origin, True, wave.minimum)


def run(graph, round_limit=10000):
    if not graph or not nx.is_connected(graph):
        raise ValueError("leader election example requires a connected graph")
    return Simulation(graph, LeaderElectionNode, CODEC, round_limit=round_limit).run()


if __name__ == "__main__":
    import networkx as nx

    print(run(nx.cycle_graph(6)))
