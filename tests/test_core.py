import unittest
import networkx as nx

from dn_simulation import AlgorithmNode, Model, Packet, SchemaCodec, Simulation


class Echo(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if ctx.round == 0 and self.node_id == 0:
            self.queue(1, "ping", self.node_id)
            ctx.finish("sent")
        elif inbox:
            ctx.finish(inbox[0][1].values[0])


class SleepReceiver(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if self.node_id == 0:
            if ctx.round == 0:
                self.queue(1, "ping", self.node_id)
                ctx.finish("sent")
        elif ctx.round == 0:
            ctx.sleep_for(1)
        elif ctx.round == 2:
            ctx.finish(tuple(inbox))


class DoubleSend(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if self.node_id == 0:
            ctx.send(1, Packet("ping", (0,)))
            ctx.send(1, Packet("ping", (0,)))


class Oversize(AlgorithmNode):
    def on_round(self, ctx, inbox):
        if self.node_id == 0:
            self.queue(1, "big", 1.0, 2.0, 3.0)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.graph = nx.path_graph(2)
        self.codec = SchemaCodec({"ping": ("id",)})

    def test_next_round_delivery_and_completion(self):
        result = Simulation(self.graph, Echo, self.codec).run()
        self.assertTrue(result.completed)
        self.assertEqual(result.rounds, 2)
        self.assertEqual(result.node_results, {0: "sent", 1: 0})
        self.assertEqual(result.sent_messages, 1)

    def test_step_and_timeout(self):
        class NeverFinishes(AlgorithmNode):
            def on_round(self, ctx, inbox):
                pass

        simulation = Simulation(self.graph, NeverFinishes, self.codec, round_limit=2)
        self.assertFalse(simulation.step().completed)
        result = simulation.run()
        self.assertFalse(result.completed)
        self.assertEqual(result.rounds, 2)

    def test_sleep_discards_message_without_waking_receiver(self):
        result = Simulation(self.graph, SleepReceiver, self.codec, model=Model.SLEEPING_CONGEST).run()
        self.assertTrue(result.completed)
        self.assertEqual(result.node_results[1], ())
        self.assertEqual(result.awake_rounds[1], 2)
        self.assertEqual(result.dropped_messages, 1)

    def test_standard_model_rejects_sleep(self):
        with self.assertRaisesRegex(ValueError, "sleep requires"):
            Simulation(self.graph, SleepReceiver, self.codec).run()

    def test_duplicate_link_send_rejected(self):
        with self.assertRaisesRegex(ValueError, "at most one"):
            Simulation(self.graph, DoubleSend, self.codec).run()

    def test_oversized_message_rejected(self):
        codec = SchemaCodec({"big": ("weight", "weight", "weight")})
        with self.assertRaisesRegex(ValueError, "exceeds CONGEST"):
            Simulation(self.graph, Oversize, codec).run()

    def test_codec_round_trip(self):
        codec = SchemaCodec({"check": ("id", "epoch", "bool", "weight")})
        packet = Packet("check", (None, 7, True, -0.0))
        self.assertEqual(codec.decode(codec.encode(packet, 5, 100), 5, 100), packet)

    def test_invalid_graph_and_weights(self):
        with self.assertRaises(ValueError):
            Simulation(nx.path_graph(2).to_directed(), Echo, self.codec)
        graph = nx.path_graph(2)
        graph.edges[0, 1]["weight"] = float("nan")
        with self.assertRaises(ValueError):
            Simulation(graph, Echo, self.codec)
        graph = nx.Graph()
        graph.add_edge(10, 20)
        self.assertEqual(set(Simulation(graph, Echo, self.codec).nodes), {10, 20})


if __name__ == "__main__":
    unittest.main()
