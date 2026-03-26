"""Base collector interfaces for topology data collection.

Provides abstract Collector class defining lifecycle methods and graph
collection strategy. All concrete collectors (socket, IPC, shared memory)
inherit from this base and implement the abstract methods.

Key Components:
    - Collector: Abstract base class with start/stop/collect lifecycle
    - Defines graph traversal pattern: seed nodes → BFS expansion → full graph
    - Thread-safe collection with configurable iteration limits

Collection Strategy:
    1. _get_seed_graph(): Initialize with starting nodes
    2. get_neighbors_with_edges(): Expand from each node
    3. collect_whole_graph(): BFS traversal with deduplication

Lifecycle Methods:
    - start(): Initialize data sources (sniffers, monitors)
    - stop(): Cleanup and shutdown
    - clear(): Reset internal state

Subclass Requirements:
    Concrete collectors must implement all abstract methods and
    should use EntityNameSpace.set_namespace() to tag entities.

Notes:
    Collection uses ignore_entity_ids and ignore_edge_ids sets to prevent
    infinite loops and duplicate processing during BFS traversal.
"""

import traceback
from abc import ABC, abstractmethod
from queue import Queue
from typing import Tuple

from anansi.common.logging import get_logger
from anansi.edge.edge import Edge
from anansi.entity.entity_base import Entity
from anansi.graph.graph import Graph

LOGGER = get_logger(__name__)


class Collector(ABC):
    """Base class for all collectors."""

    @abstractmethod
    def start(self):
        """Start the collector."""
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """Stop the collector."""
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        """Clear the collector's internal state."""
        raise NotImplementedError

    @abstractmethod
    def _get_seed_graph(self) -> Graph:
        """Get the initial graph nodes to start collection from."""
        raise NotImplementedError

    def supported_source_node_type(self) -> set[type]:
        """Get the supported entity types by this collector."""
        return {Entity}

    @abstractmethod
    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[list[Entity], list[Edge]]:
        """Get the neighbors of the given entity with edges."""
        raise NotImplementedError

    def collect_whole_graph(
        self,
        ignore_entity_ids: set[str] = None,
        ignore_edge_ids: set[str] = None,
        max_iterations: int = None,
    ) -> Graph:
        """
        Collect the whole graph.
        Each specific collector should decide the original start state.
        """
        return self._expand_graph_bfs(
            self._get_seed_graph(),
            ignore_entity_ids=ignore_entity_ids,
            ignore_edge_ids=ignore_edge_ids,
            max_iterations=max_iterations,
        )

    def expand_since_graph(
        self,
        graph: Graph,
        ignore_entity_ids: set[str] = None,
        ignore_edge_ids: set[str] = None,
        max_iterations: int = None,
    ) -> Graph:
        """Expand a graph by collecting from existing nodes."""
        return self._expand_graph_bfs(
            graph,
            ignore_entity_ids=ignore_entity_ids,
            ignore_edge_ids=ignore_edge_ids,
            max_iterations=max_iterations,
        )

    def collect_since(
        self,
        entity: Entity,
        ignore_entity_ids: set[str] = None,
        ignore_edge_ids: set[str] = None,
        max_iterations: int = None,
    ) -> Graph:
        if not isinstance(entity, Entity):
            raise TypeError("Input must be an Entity instance")
        return self._expand_graph_bfs(
            Graph(nodes=[entity], edges=[]),
            ignore_entity_ids=ignore_entity_ids,
            ignore_edge_ids=ignore_edge_ids,
            max_iterations=max_iterations,
        )

    def _expand_graph_bfs(
        self,
        graph: Graph,
        ignore_entity_ids: set[str] | None,
        ignore_edge_ids: set[str] | None,
        max_iterations: int = None,
    ) -> Graph:
        """Generic BFS expansion starting from all nodes in ``graph``."""

        if ignore_entity_ids is None:
            ignore_entity_ids = set()
        if ignore_edge_ids is None:
            ignore_edge_ids = set()

        nodes: list[Entity] = list(graph.nodes)
        edges: list[Edge] = list(graph.edges)
        gid2edge: dict[int, Edge] = {edge.global_id: edge for edge in edges}
        queue: Queue[Entity] = Queue()

        for edge in edges:
            ignore_edge_ids.add(edge.global_id)

        for node in graph.nodes:
            queue.put(node)

        iteration = 0
        while not queue.empty() and (
            max_iterations is None or iteration < max_iterations
        ):
            current_entity = queue.get()
            if current_entity.global_id in ignore_entity_ids:
                continue
            nodes.append(current_entity)
            ignore_entity_ids.add(current_entity.global_id)
            iteration += 1

            try:
                neighbors, new_edges = self.get_neighbors_with_edges(current_entity)
            except (OSError, ValueError):  # pragma: no cover - defensive path
                LOGGER.error(
                    "Failed to get neighbors from %s for entity %s: %s",
                    type(self).__name__,
                    current_entity,
                    traceback.format_exc(),
                )
                continue

            for neighbor in neighbors:
                if neighbor.global_id not in ignore_entity_ids:
                    queue.put(neighbor)

            for edge in new_edges:
                if edge.global_id in gid2edge:
                    gid2edge[edge.global_id].merge_other(edge)
                elif edge.global_id not in ignore_edge_ids:
                    ignore_edge_ids.add(edge.global_id)
                    edges.append(edge)
                    gid2edge[edge.global_id] = edge

        return Graph(nodes=sorted(nodes), edges=sorted(edges))


__all__ = ["Collector"]
