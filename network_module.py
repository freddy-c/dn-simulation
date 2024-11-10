from typing import Union, Any, List, Dict
from abc import ABC, abstractmethod
import networkx as nx


NeighbourType = Union[List[int], Dict[int, float]]


class Message:
    """Represents a message with a recipient and content."""

    def __init__(self, recipient: int, content: Any):
        """
        Initialize a Message instance.

        Args:
            recipient: The ID of the recipient node.
            content: The content of the message, can be any type.
        """
        self.recipient: int = recipient
        self.content: Any = content


class AbstractNode(ABC):
    def __init__(self, node_id: int, neighbours: List[int]):
        self.node_id: int = node_id
        self._neighbours: NeighbourType = neighbours
        self.state: Dict[str, Any] = {}
        self.inbox: List[Message] = []
        self.outbox: List[Message] = []

    def send_message(self, recipient: int, content: Any) -> None:
        message = Message(recipient=recipient, content=content)
        self.outbox.append(message)

    def recieve_message(self) -> None:
        while self.inbox:
            message = self.inbox.pop(0)
            self.handle_message(message)

    @abstractmethod
    def handle_message(self, message: Message) -> None:
        """Abstract method to handle received messages, to be implemented in subclasses."""
        pass

    @abstractmethod
    def compute(self):
        """Abstract method to handle computations, to be implemented in subclasses."""
        pass


class Network:
    """Represents a network"""

    def __init__(self, graph: nx.Graph, node_type):
        """
        Initialize a Network instance.

        Args:
            graph: A networkx graph structure.
        """
        self.graph: nx.Graph = graph
        self.nodes: Dict[int, AbstractNode] = {}
        self.node_type = node_type
        self._init_network()

    def _init_network(self) -> None:
        """Initialize nodes in the network based on the provided graph."""
        for node in self.graph.nodes():
            neighbours = list(self.graph.neighbors(node))
            self.nodes[node] = self.node_type(node_id=node, neighbours=neighbours)

    def _send(self) -> None:
        """Sends messages from each node's outbox to the recipient's inbox
        if there exists an edge in the graph between them."""
        for node in self.nodes.values():
            for message in node.outbox:
                recipient_node = self.nodes.get(message.recipient)

                # Check if an edge exists in the graph
                if recipient_node and self.graph.has_edge(
                    node.node_id, message.recipient
                ):
                    recipient_node.inbox.append(message)

            # Clear the nodes outbox after sending messages
            node.outbox.clear()

    def _recieve(self) -> None:
        for node in self.nodes.values():
            node.recieve_message()

    def _compute(self) -> None:
        for node in self.nodes.values():
            node.compute()

    def _simulate_round(self) -> None:
        self._send()
        self._recieve()
        self._compute()

    def run(self, steps: int) -> None:
        for _ in range(steps):
            self._simulate_round()

    def __str__(self) -> str:
        output = ["Network State:\n"]
        for node_id, node in self.nodes.items():
            output.append(f"Node {node_id}:\n")
            output.append(f"  State: {node.state}\n")

        return "".join(output)


class WeightedNetwork(Network):
    def _init_network(self) -> None:
        for node in self.graph.nodes():
            # Store neighbors with weights
            neighbours_with_weights = {
                neighbour: self.graph[node][neighbour].get("weight", 1.0)
                for neighbour in self.graph.neighbors(node)
            }
            self.nodes[node] = self.node_type(
                node_id=node, neighbours=neighbours_with_weights
            )
