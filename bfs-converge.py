from network_module import WeightedNetwork, AbstractNode, Message
import networkx as nx
import random


class BFSTreeNode(AbstractNode):
    def __init__(self, node_id, neighbours):
        super().__init__(node_id, neighbours)
        self.state["done"] = False
        self.state["phase"] = "bfs"
        self.state["parent"] = -1
        self.state["children"] = []
        self.state["invites"] = []
        self.state["accepts"] = []
        self.state["round"] = -1
        self.state["value"] = random.randint(1, 10)
        self.state["converges"] = []

    def send_to_neighbours(self, message) -> None:
        for neighbour in self._neighbours:
            self.send_message(neighbour, message)

    def handle_message(self, message) -> None:
        if message.content["request"] == "invite":
            self.state["invites"].append(message.content["id"])
        elif message.content["request"] == "accept":
            self.state["accepts"].append(message.content["id"])
        elif message.content["request"] == "convergecast":
            self.state["converges"].append(message.content["value"])

    def bfs(self, source_id: int, round_number: int) -> None:
        # if the node is the source node
        if self.node_id == source_id and self.state["phase"] == "bfs":
            # send “invite” message to all neighbours
            self.send_to_neighbours({"id": self.node_id, "request": "invite"})
            # designate all neighbors as child nodes
            self.state["children"] = list(self._neighbours)

            self.state["phase"] = "convergecast"
            self.state["round"] = round_number

        elif self.state["parent"] == -1 and self.state["invites"]:
            self.state["round"] = round_number + 2

            parent = self.state["invites"][0]
            # send “accept” message to exactly one neighbour
            self.send_message(parent, {"id": self.node_id, "request": "accept"})
            # designate that neighbour as parent
            self.state["parent"] = parent

            # send “invite” message to all neighbours except new parent
            potential_children = [
                neighbour for neighbour in self._neighbours if neighbour != parent
            ]

            for node in potential_children:
                self.send_message(node, {"id": self.node_id, "request": "invite"})

        elif self.state["accepts"]:
            while self.state["accepts"]:
                new_child = self.state["accepts"].pop(0)
                if new_child not in self.state["children"]:
                    self.state["children"].append(new_child)

        if round_number == self.state["round"]:
            self.state["phase"] = "convergecast"

    def convergecast(self) -> None:
        # if the node is a leaf node
        if not self.state["children"]:
            self.send_message(
                self.state["parent"],
                {"request": "convergecast", "value": self.state["value"]},
            )

            self.state["phase"] = "terminated"

        elif len(self.state["converges"]) == len(self.state["children"]):
            max_value = max(self.state["converges"] + [self.state["value"]])

            if self.state["parent"] != -1:
                self.send_message(
                    self.state["parent"],
                    {"request": "convergecast", "value": max_value},
                )

                self.state["phase"] = "terminated"
            else:
                print(
                    f"I am the root, node {self.node_id} and the max value for this network is: {max_value}"
                )
                self.state["phase"] = "terminated"

    def compute(self, round_number: int) -> None:
        if self.state["phase"] == "bfs":
            self.bfs(source_id=1, round_number=round_number)

        if self.state["phase"] == "convergecast":
            self.convergecast()


# Create an empty graph
G = nx.Graph()

# Add nodes
G.add_nodes_from([1, 2, 3, 4])

# Add edges with weights
G.add_edge(1, 2, weight=1.5)
G.add_edge(1, 3, weight=2.0)
G.add_edge(2, 3, weight=2.5)
G.add_edge(2, 4, weight=1.0)
G.add_edge(3, 4, weight=3.0)


network = WeightedNetwork(G, BFSTreeNode)
network.run(10)
print(network)
