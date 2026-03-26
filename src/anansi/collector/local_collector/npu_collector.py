"""
NPU local access sniffer for Linux/Ascend/Atlas/ARM/AI chips.
This is a stub for demonstration. Real implementation should parse /proc, device files, or use vendor SDKs.
"""

import os

from anansi.collector.local_collector.local_collector import LocalCollector
from anansi.common.logging import get_logger
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.config_manager.configs import NPUSnifferConfig
from anansi.edge.edge import Edge
from anansi.edge.structual.belong import AccessEdge
from anansi.edge.xpu.npu_access_sniffer import NPUAccessSniffer, get_npu_access_sniffer
from anansi.entity.entity_base import Entity
from anansi.entity.node_entity import NPUEntity, ProcessEntity
from anansi.graph.graph import Graph

LOGGER = get_logger(__name__)

from anansi.common.env_manager import EnvManager

if not EnvManager().has_npu():
    LOGGER.warning("NPU not available. NPUCollector will not be registered")
else:

    class NPUCollector(LocalCollector):
        """
        Collects NPU access topology graph from NPUAccessSniffer
        """

        def start(self):
            # static collect: not needed
            pass

        def stop(self):
            # static collect: not needed
            pass

        def clear(self):
            # static collect: not needed
            pass

        def __init__(self):
            mngr: GlobalConfigManager = GlobalConfigManager.get_instance()

            self.sniffer: NPUAccessSniffer = get_npu_access_sniffer(
                mngr.get_config().sniffer_config.npu_sniffer
            )

        def _get_seed_graph(self) -> Graph:
            seed_nodes: list[NPUEntity] = self.sniffer.get_all_npu_entities()
            seed_graph = Graph(nodes=seed_nodes, edges=[])
            return seed_graph

        def get_neighbors_with_edges(self, entity) -> tuple[list[Entity], list[Edge]]:
            if isinstance(entity, ProcessEntity):
                neighbors: list[NPUEntity] = self.sniffer.get_npu_ranks_accessed_by_pid(
                    entity.pid
                )
                edges = [
                    AccessEdge(source_node=entity, target_node=neighbor)
                    for neighbor in neighbors
                ]
                return neighbors, edges
            elif isinstance(entity, NPUEntity):
                neighbors: list[ProcessEntity] = self.sniffer.get_pids_accessing_npu(
                    entity
                )
                edges = [
                    AccessEdge(source_node=neighbor_process, target_node=entity)
                    for neighbor_process in neighbors
                ]
                return neighbors, edges
            return [], []

        def supported_source_node_type(self) -> set[type]:
            return {ProcessEntity, NPUEntity}
