"""Distributed minimum spanning tree by mutual fragment-edge merging.

This keeps the historical fragment/MWOE protocol, with a tree-wide update
barrier and fragment versions so cross-edge checks survive differing tree depths.
All ordering is by (weight, low endpoint, high endpoint), including ties.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import networkx as nx
from dn_simulation import AlgorithmNode, SchemaCodec, Simulation

CODEC = SchemaCodec({
    "find": ("id", "epoch"),
    "check": ("id", "epoch"),
    "checked": ("id", "epoch", "bool"),
    "report": ("id", "epoch", "bool", "weight", "id", "id"),
    "best": ("id", "epoch", "bool", "weight", "id", "id"),
    "merge": ("id", "epoch", "weight", "id", "id"),
    "update": ("id", "epoch", "id", "epoch", "id", "epoch"),
    "updated": ("id", "epoch"),
    "halt": ("id", "epoch"),
})

Key = tuple[float, int, int]
Fragment = tuple[int, int]


def key_fields(key: Key | None):
    return (False, 0.0, None, None) if key is None else (True, *key)


def read_key(has_edge, weight, u, v):
    return (weight, u, v) if has_edge else None


@dataclass(frozen=True)
class MSTResult:
    fragment: Fragment
    branch_neighbors: tuple[int, ...]


class MSTNode(AlgorithmNode):
    def __init__(self, node_id, neighbors):
        super().__init__(node_id, neighbors)
        self.fragment: Fragment = (node_id, 0)
        self.epoch_counter = 0
        self.history: set[Fragment] = set()
        self.edge_state = {neighbor: "basic" for neighbor in neighbors}
        self.phase = "search"
        self.parent: int | None = None
        self.children: set[int] = set()
        self.pending: set[int] = set()
        self.local_key: Key | None = None
        self.subtree_key: Key | None = None
        self.checking: int | None = None
        self.best_key: Key | None = None
        self.merge_target: int | None = None
        self.merge_requests: list[tuple[int, Fragment, Key]] = []
        self.update_parent: int | None = None
        self.update_pending: set[int] = set()
        self.started = False

    def edge_key(self, neighbor):
        return (self.neighbors[neighbor], min(self.node_id, neighbor), max(self.node_id, neighbor))

    def branch_neighbors(self):
        return [v for v, state in self.edge_state.items() if state == "branch"]

    def send_fragment(self, neighbor, kind, *values):
        self.queue(neighbor, kind, *self.fragment, *values)

    def start_search(self):
        self.phase = "finding"
        self.parent = None
        self.children = set()
        self.pending = set(self.branch_neighbors())
        self.local_key = None
        self.subtree_key = None
        self.checking = None
        self.best_key = None
        self.merge_target = None
        for neighbor in self.pending:
            self.send_fragment(neighbor, "find")
        self.find_candidate()

    def find_candidate(self):
        candidates = (v for v, state in self.edge_state.items() if state == "basic")
        candidate = min(candidates, key=self.edge_key, default=None)
        self.checking = candidate
        if candidate is not None:
            self.send_fragment(candidate, "check")
        else:
            self.local_key = None
            self.phase = "reporting"

    def maybe_report(self):
        if self.phase != "reporting" or self.pending:
            return
        keys = [key for key in (self.local_key, self.subtree_key) if key is not None]
        best = min(keys, default=None)
        self.phase = "await_best"
        if self.parent is None:
            self.broadcast_best(best)
        else:
            self.send_fragment(self.parent, "report", *key_fields(best))

    def broadcast_best(self, key):
        self.best_key = key
        self.phase = "merging"
        if key is None:
            self._outbound.clear()
            for neighbor in self.branch_neighbors():
                self.send_fragment(neighbor, "halt")
            self.complete()
            return
        for neighbor in self.branch_neighbors():
            self.send_fragment(neighbor, "best", *key_fields(key))
        if self.local_key == key:
            self.merge_target = key[2] if key[1] == self.node_id else key[1]
            self.send_fragment(self.merge_target, "merge", *key)
        self.process_merge_requests()

    def complete(self):
        self.phase = "halted"
        self.done = True
        self.result = MSTResult(self.fragment, tuple(sorted(self.branch_neighbors())))

    def process_merge_requests(self):
        if self.phase != "merging" or self.merge_target is None:
            return
        for sender, other_fragment, key in list(self.merge_requests):
            if sender == self.merge_target and key == self.best_key and other_fragment != self.fragment:
                if self.node_id < sender:
                    # The other endpoint may have discarded our earlier request
                    # while its fragment was being updated. Repeat it now.
                    self.send_fragment(sender, "merge", *key)
                    self.merge_requests.remove((sender, other_fragment, key))
                else:
                    self.commit(sender, other_fragment)
                return

    def commit(self, sender, other_fragment):
        if self.node_id < sender:
            return  # the higher endpoint initiates the single update flood
        previous = self.fragment
        self.epoch_counter += 1
        self.fragment = (self.node_id, self.epoch_counter)
        self.history.update((previous, other_fragment))
        self.edge_state[sender] = "branch"
        self.phase = "updating"
        self.merge_requests.clear()
        self.update_parent = None
        self.update_pending = set(self.branch_neighbors())
        for neighbor in self.update_pending:
            self.send_fragment(neighbor, "update", *previous, *other_fragment)
        self.maybe_finish_update()

    def maybe_finish_update(self):
        if self.phase != "updating" or self.update_pending:
            return
        if self.update_parent is None:
            self.start_search()
        else:
            self.send_fragment(self.update_parent, "updated")
            self.phase = "waiting_find"

    def on_round(self, ctx, inbox):
        if not self.started:
            self.started = True
            if not self.neighbors:
                self.complete()
                return
            self.start_search()
        for sender, packet in inbox:
            kind, values = packet.kind, packet.values
            if kind == "halt":
                if tuple(values) != self.fragment:
                    continue
                self._outbound.clear()
                for neighbor in self.branch_neighbors():
                    if neighbor != sender:
                        self.send_fragment(neighbor, "halt")
                self.complete()
                return
            if kind == "check":
                query = tuple(values)
                internal = query == self.fragment or query in self.history
                self.send_fragment(sender, "checked", internal)
                if internal and self.edge_state[sender] == "basic":
                    self.edge_state[sender] = "rejected"
                continue
            if kind == "checked":
                other = tuple(values[:2])
                internal = values[2] or other == self.fragment or other in self.history
                if self.checking != sender or self.phase != "finding":
                    continue
                self.checking = None
                if internal:
                    self.edge_state[sender] = "rejected"
                    self.find_candidate()
                else:
                    self.local_key = self.edge_key(sender)
                    self.phase = "reporting"
                continue
            if kind == "update":
                new_fragment = tuple(values[:2])
                previous = tuple(values[2:4])
                other_previous = tuple(values[4:6])
                if new_fragment == self.fragment:
                    continue
                if self.fragment not in (previous, other_previous):
                    continue  # obsolete update from a former generation
                self.history.update((previous, other_previous))
                self.fragment = new_fragment
                self.edge_state[sender] = "branch"
                self.phase = "updating"
                self.merge_requests.clear()
                self.update_parent = sender
                self.update_pending = set(self.branch_neighbors()) - {sender}
                for neighbor in self.update_pending:
                    self.send_fragment(neighbor, "update", *previous, *other_previous)
                self.maybe_finish_update()
                continue
            if kind == "updated":
                if tuple(values) == self.fragment and self.phase == "updating":
                    self.update_pending.discard(sender)
                    self.maybe_finish_update()
                continue
            if kind == "merge":
                other_fragment = tuple(values[:2])
                key = tuple(values[2:])
                if other_fragment != self.fragment and other_fragment not in self.history:
                    self.merge_requests.append((sender, other_fragment, key))
                    self.process_merge_requests()
                continue
            if kind == "find":
                if tuple(values) != self.fragment or self.phase == "updating":
                    continue
                self.phase = "finding"
                self.parent = sender
                self.children = set()
                self.pending = set(self.branch_neighbors()) - {sender}
                self.local_key = None
                self.subtree_key = None
                self.checking = None
                self.best_key = None
                self.merge_target = None
                for neighbor in self.pending:
                    self.send_fragment(neighbor, "find")
                self.find_candidate()
                continue
            if kind == "report":
                if tuple(values[:2]) != self.fragment or sender not in self.pending:
                    continue
                self.pending.remove(sender)
                self.children.add(sender)
                key = read_key(*values[2:])
                if key is not None:
                    self.subtree_key = min((key, self.subtree_key), key=lambda k: k if k is not None else (math.inf, math.inf, math.inf))
                continue
            if kind == "best":
                if tuple(values[:2]) != self.fragment:
                    continue
                self.best_key = read_key(*values[2:])
                self.phase = "merging"
                for neighbor in self.branch_neighbors():
                    if neighbor != sender:
                        self.send_fragment(neighbor, "best", *key_fields(self.best_key))
                if self.local_key == self.best_key and self.best_key is not None:
                    self.merge_target = self.best_key[2] if self.best_key[1] == self.node_id else self.best_key[1]
                    self.send_fragment(self.merge_target, "merge", *self.best_key)
                else:
                    self.merge_target = None
                self.process_merge_requests()
        self.maybe_report()


def run(graph, *, round_limit=10000):
    if not graph or not nx.is_connected(graph):
        raise ValueError("MST example requires a connected graph")
    simulation = Simulation(graph, MSTNode, CODEC, round_limit=round_limit)
    result = simulation.run()
    return result


def edges(result):
    """Collect branch edges from locally produced results after completion."""
    if not result.completed:
        raise ValueError("MST has not completed")
    return {tuple(sorted((u, v))) for u, node_result in result.node_results.items() for v in node_result.branch_neighbors}


if __name__ == "__main__":
    import networkx as nx

    graph = nx.Graph()
    graph.add_weighted_edges_from([(0, 1, 0), (1, 2, 2), (0, 2, 2)])
    outcome = run(graph)
    print(outcome)
    print(edges(outcome))
