"""Optional graph drawing for example outputs."""
from __future__ import annotations


def draw_graph(graph, *, selected_edges=(), annotations=None, seed=42):
    """Return a Matplotlib figure and axes, highlighting selected edges.

    Requires the optional ``visualization`` dependency. Edge colors are based
    only on the caller's output; drawing does not affect the simulation.
    """
    import matplotlib.pyplot as plt
    import networkx as nx

    selected = {frozenset(edge) for edge in selected_edges}
    position = nx.spring_layout(graph, seed=seed)
    figure, axes = plt.subplots(figsize=(10, 8))
    nx.draw_networkx_nodes(graph, position, ax=axes, node_color="lightblue")
    nx.draw_networkx_labels(graph, position, ax=axes)
    nx.draw_networkx_edges(
        graph,
        position,
        ax=axes,
        edge_color=["tab:orange" if frozenset(edge) in selected else "0.7" for edge in graph.edges()],
        width=2,
    )
    weights = nx.get_edge_attributes(graph, "weight")
    if weights:
        nx.draw_networkx_edge_labels(graph, position, edge_labels=weights, ax=axes)
    if annotations:
        for node, label in annotations.items():
            x, y = position[node]
            axes.text(x, y - 0.08, str(label), ha="center", va="top", fontsize=8)
    axes.set_axis_off()
    return figure, axes
