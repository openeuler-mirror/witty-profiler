"""Aggregates multiple collectors into a single unified collector.

Provides CollectorSet, a composite collector that manages multiple concrete
collectors (socket, IPC, shared memory) and coordinates their lifecycle,
merging their graph results into a unified topology view.

Features:
    - Aggregates lifecycle calls (start/stop/clear) to all subcollectors
    - Merges seed graphs from all collectors via Graph.merge_graphs()
    - Deduplicates entities and edges across collector results
    - Provides unified neighbor discovery across all data sources

Graph Merging:
    When multiple collectors discover the same entity (by global_id),
    the Graph constructor automatically deduplicates via GlobalIDManager.
    This ensures processes appear once even if discovered by multiple collectors.

Usage:
    ```python
    collectors = CollectorSet(subcollectors=[
        SocketCollector(),
        SharedMemoryCollector(),
        IPCCollector(),
    ])
    collectors.start()
    graph = collectors.collect_whole_graph()
    collectors.stop()
    ```

Notes:
    Collector order doesn't affect final result due to deduplication.
    Each collector must be a RegisteredCollector subclass.
"""

import collections
from typing import Tuple

from anansi.collector.collector_base import Collector
from anansi.common.logging import VERBOSE, get_logger
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.edge.edge import Edge
from anansi.entity.entity_base import Entity
from anansi.graph.graph import Graph

LOGGER = get_logger(__name__)


class CollectorSet(Collector):
    def __init__(self, subcollectors: list[Collector]):
        LOGGER.verbose(
            "Initializing CollectorSet with %s subcollectors: %s",
            len(subcollectors),
            [type(e).__name__ for e in subcollectors],
        )
        self.subcollectors = [e for e in subcollectors if isinstance(e, Collector)]
        LOGGER.verbose(
            "Initializing CollectorSet with %s valid subcollectors: %s",
            len(self.subcollectors),
            [type(e).__name__ for e in self.subcollectors],
        )
        self.entity_type2collector: dict[type, list[Collector]] = {}
        for collector in self.subcollectors:
            for entity_type in collector.supported_source_node_type():
                self.entity_type2collector.setdefault(entity_type, []).append(collector)
        self._start_status: bool = False

    @property
    def start_status(self) -> bool:
        return self._start_status

    def start(self):
        if self._start_status:
            LOGGER.warning("CollectorSet already started")
            return
        for collector in self.subcollectors:
            collector.start()
        self._start_status = True

    def stop(self):
        if not self._start_status:
            LOGGER.warning("CollectorSet already stopped")
            return
        for collector in self.subcollectors:
            collector.stop()
        self._start_status = False

    def clear(self):
        for collector in self.subcollectors:
            collector.clear()

    def _get_seed_graph(self) -> Graph:
        LOGGER.verbose("Collecting seed graphs from subcollectors...")
        seed_candidates = (
            GlobalConfigManager().get_config().collector_config.seed_graph_collectors
        )
        subgraphs = []
        for collector in self.subcollectors:
            # 从NPUCollector中获取种子图
            if type(collector).__name__ not in seed_candidates:
                continue
            try:
                subgraphs.append(collector._get_seed_graph())
            except Exception as e:
                LOGGER.error(
                    "Failed to get seed graph from %s: %s",
                    type(collector).__name__,
                    e,
                )
                import traceback

                traceback.print_exc()
        graph = Graph.merge_graphs(subgraphs)
        LOGGER.verbose("Collected seed graphs from subcollectors: %s", graph)
        return graph

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[list[Entity], list[Edge]]:
        nodes = []
        edges = []
        if type(entity) not in self.entity_type2collector:
            supported_collectors = []
            for collector in self.subcollectors:
                for entity_type in collector.supported_source_node_type():
                    if isinstance(entity, entity_type):
                        supported_collectors.append(collector)
                        break
            self.entity_type2collector[type(entity)] = supported_collectors
        supported_collectors = self.entity_type2collector.get(type(entity), [])
        if not supported_collectors:
            return nodes, edges

        for collector in supported_collectors:
            try:
                sub_nodes, sub_edges = collector.get_neighbors_with_edges(entity)
                nodes.extend(sub_nodes)
                edges.extend(sub_edges)
            except (OSError, ValueError) as e:
                LOGGER.error(
                    "Failed to get neighbors from %s for entity %s: %s",
                    type(collector).__name__,
                    entity,
                    e,
                )
                import traceback

                traceback.print_exc()
        if LOGGER.isEnabledFor(VERBOSE):
            LOGGER.verbose(
                "Collected neighbors and edges from subcollectors: %s edges, %s nodes",
                len(edges),
                len(nodes),
            )
            LOGGER.verbose(
                "Neighbors of %s: %s",
                entity,
                collections.Counter(map(lambda x: type(x).__name__, nodes)),
            )
        return nodes, edges

    def add_collector(self, collector: Collector):
        if not isinstance(collector, Collector):
            LOGGER.error("Input is not a Collector instance")
            return
        if self._start_status:
            collector.start()
        self.subcollectors.append(collector)
