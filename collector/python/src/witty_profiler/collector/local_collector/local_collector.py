"""Base collector interfaces and registry for topology data collection.

Defines the Collector abstract base class and CollectorRegistry metaclass
that all concrete collectors (socket, IPC, shared memory) must inherit.
Provides generic graph expansion algorithms and lifecycle hooks.

Key Components:
    - Collector: ABC defining start/stop/clear and graph collection methods
    - CollectorRegistry: Metaclass auto-registering concrete collector subclasses
    - RegisteredCollector: Base class combining ABC and CollectorRegistry

Abstract Methods (must be implemented by subclasses):
    - _get_seed_graph(): Return initial graph nodes to start collection
    - get_neighbors_with_edges(): Given an entity, discover its neighbors
    - start(): Begin data collection (idempotent)
    - stop(): End data collection
    - clear(): Reset internal state

Graph Collection Methods (template pattern):
    - collect_whole_graph(): BFS expansion from seed graph
    - expand_since_graph(): BFS expansion from existing graph
    - collect_since(): BFS expansion from single entity
    - _expand_graph_bfs(): Generic BFS implementation

Parameters:
    ignore_entity_ids: Set of entity global_ids to skip during expansion
    ignore_edge_ids: Set of edge global_ids to skip during expansion
    max_iterations: Limit BFS expansion iterations for bounded collection

Notes:
    All collectors must be thread-safe for their respective data sources.
    The BFS expansion skips OSError/ValueError during neighbor discovery.
    Collectors register automatically via CollectorRegistry metaclass.
"""

from abc import ABC, ABCMeta, abstractmethod
from queue import Queue
from typing import Tuple

from witty_profiler.collector.collector_base import Collector
from witty_profiler.common.logging import get_logger
from witty_profiler.edge.edge import Edge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class LocalCollectorRegistry(ABCMeta):
    """Metaclass for all collectors."""

    _registry: dict[str, type] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if hasattr(cls, "__abstractmethods__") and cls.__abstractmethods__:
            return cls
        if name not in mcs._registry:
            LOGGER.debug(f"Registering LocalCollector: {name}")
            mcs._registry[name] = cls
        return cls

    @classmethod
    def get_collectors(mcs) -> dict[str, type]:
        return mcs._registry.copy()


class LocalCollector(Collector, metaclass=LocalCollectorRegistry):
    pass


def get_local_collectors() -> dict[str, type]:
    """Get all available collector types."""
    return LocalCollectorRegistry.get_collectors()


class StaticLocalCollector(LocalCollector):
    """A simple local collector that does not require any setup or teardown."""

    def start(self):
        pass

    def stop(self):
        pass

    def clear(self):
        pass


__all__ = ["get_local_collectors", "LocalCollector"]
