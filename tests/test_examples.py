import random
import unittest
import networkx as nx

from examples.broadcast import neighbor_ids, neighbor_max_weights
from examples.bfs_max import run as run_bfs
from examples.leader_election import run as run_election
from examples.mst import edges as mst_edges, run as run_mst
from examples.sleeping_broadcast import run as run_sleeping_broadcast


class ExampleTests(unittest.TestCase):
    def test_broadcasts(self):
        graph = nx.path_graph(4)
        graph.edges[0, 1]["weight"] = -3
        graph.edges[1, 2]["weight"] = 2
        graph.edges[2, 3]["weight"] = 0
        self.assertEqual(neighbor_ids(graph).node_results[1], {0: 0, 2: 2})
        self.assertEqual(neighbor_max_weights(graph).node_results[2], {1: 2.0, 3: 0.0})
        sleeping = run_sleeping_broadcast(graph)
        self.assertTrue(sleeping.completed)
        self.assertEqual(sleeping.node_results[1], {0: 0, 2: 2})
        self.assertEqual(set(sleeping.awake_rounds.values()), {3})

    def test_singleton_and_disconnected_inputs(self):
        graph = nx.empty_graph(1)
        self.assertEqual(neighbor_ids(graph).node_results, {0: {}})
        self.assertEqual(run_election(graph).node_results, {0: 0})
        self.assertEqual(run_bfs(graph, source=0, values={0: -2}).node_results[0]["maximum"], -2)
        self.assert_mst(graph)
        disconnected = nx.empty_graph(2)
        for algorithm in (
            lambda: run_election(disconnected),
            lambda: run_bfs(disconnected, source=0, values={0: 0, 1: 1}),
            lambda: run_mst(disconnected),
        ):
            with self.assertRaisesRegex(ValueError, "connected graph"):
                algorithm()

    def test_bfs_and_convergecast(self):
        for n in range(2, 12):
            graph = nx.gnp_random_graph(n, 0.4, seed=n)
            if not nx.is_connected(graph):
                continue
            values = {i: float(i - 4) for i in graph}
            result = run_bfs(graph, source=0, values=values)
            self.assertTrue(result.completed)
            for node, state in result.node_results.items():
                self.assertEqual(state["distance"], nx.shortest_path_length(graph, 0, node))
                self.assertEqual(state["maximum"], max(values.values()))
                if node:
                    self.assertEqual(state["distance"], result.node_results[state["parent"]]["distance"] + 1)

    def test_leader_election(self):
        for n in range(2, 12):
            graph = nx.gnp_random_graph(n, 0.45, seed=100 + n)
            if not nx.is_connected(graph):
                continue
            result = run_election(graph)
            self.assertTrue(result.completed)
            self.assertEqual(set(result.node_results.values()), {0})

    def test_mst_saved_race_and_small_edge_cases(self):
        graph = nx.Graph()
        graph.add_weighted_edges_from([(0, 18, 38), (18, 7, 29), (18, 15, 37), (18, 16, 43), (1, 5, 39), (1, 19, 5), (1, 10, 1), (5, 14, 33), (5, 10, 21), (5, 7, 26), (19, 6, 18), (10, 14, 17), (10, 15, 45), (2, 3, 2), (2, 13, 13), (2, 15, 20), (3, 17, 32), (3, 9, 22), (3, 4, 12), (3, 15, 48), (13, 15, 7), (15, 6, 47), (15, 17, 40), (17, 12, 24), (17, 14, 10), (4, 7, 34), (7, 6, 11), (7, 16, 31), (14, 6, 27), (16, 12, 8)])
        result = run_mst(graph)
        self.assertTrue(result.completed)
        self.assertEqual(mst_edges(result), {tuple(sorted(edge)) for edge in nx.minimum_spanning_tree(graph).edges()})
        for edges in [[(0, 1, 0)], [(0, 1, 1), (0, 2, 3), (0, 3, 2), (1, 2, 2), (1, 3, 2)]]:
            graph = nx.Graph()
            graph.add_weighted_edges_from(edges)
            self.assert_mst(graph)
        graph = nx.Graph()
        graph.add_weighted_edges_from([(0, 1, -0.0), (1, 2, -2.5), (0, 2, 0.25), (2, 3, -2.5)])
        self.assert_mst(graph)

    def assert_mst(self, graph):
        result = run_mst(graph, round_limit=5000)
        self.assertTrue(result.completed)
        actual = mst_edges(result)
        inferred = nx.Graph()
        inferred.add_nodes_from(graph)
        inferred.add_edges_from(actual)
        self.assertTrue(nx.is_tree(inferred))
        self.assertEqual(len(actual), len(graph) - 1)
        self.assertEqual(sum(graph.edges[edge]["weight"] for edge in actual), nx.minimum_spanning_tree(graph).size(weight="weight"))
        for u, v in actual:
            self.assertIn(v, result.node_results[u].branch_neighbors)
            self.assertIn(u, result.node_results[v].branch_neighbors)

    def test_mst_random_weights_and_ties(self):
        for case in range(250):
            rng = random.Random(case)
            n = 2 + case % 23
            graph = nx.random_labeled_tree(n, seed=case)
            possible = [(u, v) for u in range(n) for v in range(u + 1, n) if not graph.has_edge(u, v)]
            rng.shuffle(possible)
            graph.add_edges_from(possible[:case % (2 * n)])
            for edge in graph.edges():
                graph.edges[edge]["weight"] = rng.randrange(-10, 11)
            self.assert_mst(graph)


if __name__ == "__main__":
    unittest.main()
