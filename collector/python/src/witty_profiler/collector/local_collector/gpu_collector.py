"""
GPU local access sniffer for Linux/NVIDIA GPUs.
This is a stub for demonstration. Real implementation should parse /proc, device files, or use vendor SDKs.
"""

import os

from witty_profiler.collector.local_collector.local_collector import LocalCollector
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.config_manager.configs import GPUSnifferConfig
from witty_profiler.edge.edge import Edge
from witty_profiler.edge.structual.belong import AccessEdge
from witty_profiler.edge.xpu.gpu_access_sniffer import GPUAccessSniffer, get_gpu_access_sniffer
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity import GPUEntity, ProcessEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


from witty_profiler.common.env_manager import EnvManager

if not EnvManager().has_gpu():
    LOGGER.warning("GPU not available. GPUCollector will not be registered")
else:

    class GPUCollector(LocalCollector):
        """
        Collects GPU access topology graph from GPUAccessSniffer
        """

        def start(self):
            pass

        def stop(self):
            pass

        def clear(self):
            pass

        def __init__(self):
            mngr: GlobalConfigManager = GlobalConfigManager.get_instance()

            self.sniffer: GPUAccessSniffer = get_gpu_access_sniffer(
                mngr.get_config().sniffer_config.gpu_sniffer
            )

        def _get_seed_graph(self) -> Graph:
            seed_nodes: list[GPUEntity] = self.sniffer.get_all_gpu_entities()
            seed_graph = Graph(nodes=seed_nodes, edges=[])
            return seed_graph

        def get_neighbors_with_edges(self, entity) -> tuple[list[Entity], list[Edge]]:
            if isinstance(entity, ProcessEntity):
                neighbors: list[GPUEntity] = self.sniffer.get_gpu_ranks_accessed_by_pid(
                    entity.pid
                )
                edges = [
                    AccessEdge(source_node=entity, target_node=neighbor)
                    for neighbor in neighbors
                ]
                return neighbors, edges
            elif isinstance(entity, GPUEntity):
                neighbors: list[ProcessEntity] = self.sniffer.get_pids_accessing_gpu(
                    entity
                )
                edges = [
                    AccessEdge(source_node=neighbor_process, target_node=entity)
                    for neighbor_process in neighbors
                ]
                return neighbors, edges
            return [], []

        def supported_source_node_type(self) -> set[type]:
            return {ProcessEntity, GPUEntity}
