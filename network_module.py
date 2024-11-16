from typing import Union, Any, List, Dict
from abc import ABC, abstractmethod
import networkx as nx
import matplotlib.pyplot as plt
from enum import Enum


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
        self.message_queue: List[Message] = []
        self.outbox: List[Message] = []
        self.termination_round: int = None

    def send_message(self, recipient: int, content: Any) -> None:
        message = Message(recipient=recipient, content=content)
        self.outbox.append(message)

    @abstractmethod
    def compute(self, round_number: int):
        """Abstract method to handle computations, to be implemented in subclasses."""
        pass


class Network:
    """Represents a network"""

    def __init__(self, graph: nx.Graph, node_type: AbstractNode):
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
        """Sends messages from each node's outbox to the recipient's message queue."""
        for node in self.nodes.values():
            for message in node.outbox:
                recipient_node = self.nodes.get(message.recipient)

                if recipient_node and self.graph.has_edge(
                    node.node_id, message.recipient
                ):
                    recipient_node.message_queue.append(message)

            node.outbox.clear()

    def _compute(self, round_number: int) -> None:
        for node in self.nodes.values():
            node.compute(round_number)

    def _simulate_round(self, round_number: int) -> None:
        self._send()
        self._compute(round_number)

    def run(self, rounds: int) -> None:
        """
        Simulates the network operation for a given number of rounds.
        Args:
            rounds (int): The number of rounds to simulate.
        Returns:
            None
        """
        for i in range(rounds):
            self._simulate_round(round_number=i)

    def max_rounds(self) -> int:
        """
        Calculate the maximum number of rounds among all nodes in the network.

        Returns:
            int: The maximum number of rounds.
        """
        return max(node.termination_round for _, node in self.nodes.items())

    # def __str__(self) -> str:
    #     output = ["Network State:\n"]
    #     for node_id, node in self.nodes.items():
    #         output.append(f"Node {node_id}:\n")
    #         output.append(f"  State: {node.state}\n")

    #     return "".join(output)
    def __str__(self) -> str:
        output = ["Network State:\n"]
        for node_id, node in self.nodes.items():
            output.append(f"Node {node_id}:\n")
            for attr, value in vars(node).items():
                output.append(f"  {attr}: {value}\n")
        return "".join(output)


class WeightedNetwork(Network):
    """
    A class representing a weighted network that extends the base Network class.
    Methods
    """

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


def visualize_graph(
    graph,
    nodes,
    title="Graph Visualization",
    node_states_to_display=None,
    show_mst_edges=True,
):
    """
    Visualize a graph with optional MST edges and customizable node states.

    Args:
        graph (nx.Graph): The graph to visualize.
        nodes (dict): A dictionary of nodes and their states.
        title (str): The title of the plot.
        node_states_to_display (list of str): List of node state keys to display (e.g., ["parent", "value"]).
        show_mst_edges (bool): Whether to highlight MST edges.
    """
    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(graph)  # Positioning for all nodes

    # Extract MST edges (branch edges) based on node states
    mst_edges = set()
    if show_mst_edges:
        for node_id, node_data in nodes.items():
            adjacent_edges = getattr(node_data, "adjacent_edges", {})
            for neighbor_id, edge_data in adjacent_edges.items():
                if str(edge_data["status"]) == "EdgeState.BRANCH":
                    mst_edges.add(
                        (min(node_id, neighbor_id), max(node_id, neighbor_id))
                    )

    # Set edge colors based on whether they're part of the MST
    edge_colors = []
    for edge in graph.edges():
        if (min(edge), max(edge)) in mst_edges:
            edge_colors.append("orange")  # Highlight MST edges
        else:
            edge_colors.append("gray")

    # Draw nodes with labels
    node_colors = "lightblue"
    nx.draw(
        graph,
        pos,
        with_labels=True,
        node_color=node_colors,
        edge_color=edge_colors,
        node_size=500,
        font_size=12,
        width=2,
    )

    # Add edge weights as labels if present
    edge_labels = {}
    for u, v in graph.edges():
        weight = graph[u][v].get("weight", None)  # Retrieve weight if present
        if weight is not None:
            edge_labels[(u, v)] = f"{weight}"  # Display weight for weighted graphs

    nx.draw_networkx_edge_labels(
        graph, pos, edge_labels=edge_labels, font_color="black"
    )

    # Optionally display each node's specified state values
    if node_states_to_display:
        for node_id, (x, y) in pos.items():
            node_data = nodes[node_id]

            # Display specified states (e.g., "parent", "value") for each node
            for i, state_key in enumerate(node_states_to_display):
                state_value = getattr(node_data, state_key, None)
                plt.text(
                    x,
                    y - 0.05 - (i * 0.1),
                    f"{state_key.capitalize()}: {state_value}",
                    ha="center",
                    fontsize=8,
                )

    plt.title(title)
    plt.show()
