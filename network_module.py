from typing import Union, Any, List, Dict
from abc import ABC, abstractmethod
import networkx as nx
import matplotlib.pyplot as plt


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
        self.termination_round: int = None

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
    def compute(self, round_number: int):
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

    def _compute(self, round_number: int) -> None:
        for node in self.nodes.values():
            node.compute(round_number)

    def _simulate_round(self, round_number: int) -> None:
        self._send()
        self._recieve()
        self._compute(round_number)

    def run(self, rounds: int) -> None:
        for i in range(rounds):
            self._simulate_round(round_number=i)

    def max_rounds(self) -> int:
        return max(node.termination_round for _, node in self.nodes.items())

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


def visualize_graph(
    graph,
    nodes,
    title="Graph Visualization",
    node_states_to_display=None,
    show_bfs_tree=True,
):
    """
    Visualize a graph with optional BFS tree edges and customizable node states.

    Args:
        graph (nx.Graph): The graph to visualize.
        nodes (dict): A dictionary of nodes and their states.
        title (str): The title of the plot.
        node_states_to_display (list of str): List of node state keys to display (e.g., ["parent", "value"]).
        show_bfs_tree (bool): Whether to highlight BFS tree edges.
    """
    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(graph)  # Positioning for all nodes

    # Calculate BFS tree edges based on each node's "parent" state
    bfs_tree_edges = []
    if show_bfs_tree:
        for node_id, node in nodes.items():
            parent = node.state.get("parent", None)
            if (
                parent is not None and parent != -1
            ):  # Only add valid parent-child relationships
                bfs_tree_edges.append((parent, node_id))

    # Set edge colors based on whether they're part of the BFS tree
    edge_colors = []
    for edge in graph.edges():
        if show_bfs_tree and (
            edge in bfs_tree_edges or (edge[1], edge[0]) in bfs_tree_edges
        ):
            edge_colors.append("orange")  # Highlight BFS tree edges
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

    # Display each node's specified state values
    for node_id, (x, y) in pos.items():
        node = nodes[node_id]

        # Display specified states (e.g., "parent", "children", "value") for each node
        if node_states_to_display:
            for i, state_key in enumerate(node_states_to_display):
                state_value = node.state.get(state_key, None)
                plt.text(
                    x,
                    y - 0.05 - (i * 0.1),
                    f"{state_key.capitalize()}: {state_value}",
                    ha="center",
                    fontsize=8,
                )

    plt.title(title)
    plt.show()
