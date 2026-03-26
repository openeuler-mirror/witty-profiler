"""
RDMA topology:
    Process -Own→ RDMA Protection Domain (RdmaProtectionDomain)
    RdmaProtectionDomain -Own→ RDMA Queue Pair (RdmaQueuePair)
    RdmaProtectionDomain -Own→ RdmaMemoryRegion
    RdmaProtectionDomain -Access→ RDMA Device (RdmaDevice)
    RdmaQueuePair -Connect→ RdmaQueuePair
"""

from anansi.collector.local_collector.local_collector import LocalCollector
from anansi.common.id_manager import GlobalIDManager
from anansi.common.logging import get_logger
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.edge.edge import Edge
from anansi.edge.rdma.rdma_sniffer import RDMASniffer
from anansi.edge.structual.attribute import HasAttributeEdge
from anansi.edge.structual.belong import AccessEdge, OwnEdge
from anansi.edge.structual.connection import ConnectToEdge
from anansi.entity.entity_base import Entity
from anansi.entity.node_entity.node_entity import ProcessEntity
from anansi.entity.node_entity.rdma import (
    QPNManager,
    RdmaDevice,
    RdmaLocalQueuePair,
    RdmaMemoryRegion,
    RdmaProtectionDomain,
    RdmaStatisticPerSecond,
)
from anansi.graph.graph import Graph

LOGGER = get_logger(__name__)


class RDMACollector(LocalCollector):
    """
    Collects RDMA topology graph from RDMA Sniffer
    """

    def start(self):
        self._rdma_sniffer.start()

    def stop(self):
        self._rdma_sniffer.stop()

    def clear(self):
        self._rdma_sniffer.clear()

    def __init__(self):
        self._rdma_sniffer = RDMASniffer()
        mngr = GlobalConfigManager()
        self.config = mngr.get_config().collector_config.rdma_collector_config

    def supported_source_node_type(self):
        return {ProcessEntity, RdmaProtectionDomain, RdmaLocalQueuePair, RdmaDevice}

    def _get_seed_graph(self) -> Graph:
        """Return the RDMA topology graph"""
        QPNManager().clear()  # clear QPN cache to avoid stale data

        pids: list[int] = self._rdma_sniffer.get_all_pid_accessing_rdma()
        process_entities = [
            ProcessEntity.create_ensure_unique_id(pid=pid) for pid in pids
        ]
        return Graph(nodes=process_entities, edges=[])

    def get_neighbors_with_edges(
        self,
        entity: ProcessEntity | RdmaProtectionDomain | RdmaLocalQueuePair | RdmaDevice,
    ) -> tuple[list[Entity], list[Edge]]:
        """
        Find Neighbor Entities for RDMA topology:

            Process -Own→ RDMA Protection Domain (RdmaProtectionDomain)
            RdmaProtectionDomain -Own→ RDMA Queue Pair (RdmaQueuePair)
            RdmaProtectionDomain -Own→ RdmaMemoryRegion
            RdmaProtectionDomain -Access→ RDMA Device (RdmaDevice)
            RdmaQueuePair -Connect→ RdmaQueuePair

        The RdmaStatisticPerSecond of RdmaDevice is dynamically changing
        """
        if isinstance(entity, ProcessEntity):
            return self._get_process_neighbors_with_edges(entity)
        elif isinstance(entity, RdmaProtectionDomain):
            return self._get_pd_neighbors_with_edges(entity)
        elif isinstance(entity, RdmaLocalQueuePair):
            return self._get_qp_neighbors_with_edges(entity)
        elif isinstance(entity, RdmaDevice):
            return self._get_device_neighbors_with_edges(entity)
        else:
            return [], []

    def _get_process_neighbors_with_edges(
        self, process_entity: ProcessEntity
    ) -> tuple[list[Entity], list[Edge]]:
        neighbors = []
        edges = []
        neighbors: list[RdmaProtectionDomain] = self._rdma_sniffer.get_pds_by_pid(
            process_entity.pid
        )
        for pd in neighbors:
            edges.append(
                OwnEdge.create_ensure_unique_id(
                    source_node=process_entity,
                    target_node=pd,
                )
            )
        return neighbors, edges

    def _get_pd_neighbors_with_edges(
        self, pd_entity: RdmaProtectionDomain
    ) -> tuple[list[Entity], list[Edge]]:
        neighbors = []
        edges = []
        qp_neighbors: list[RdmaLocalQueuePair] = self._rdma_sniffer.get_qps_by_pdn(
            pd_entity
        )
        for qp in qp_neighbors:
            neighbors.append(qp)
            edges.append(
                OwnEdge.create_ensure_unique_id(
                    source_node=pd_entity,
                    target_node=qp,
                )
            )
        mr_neighbors: list[RdmaMemoryRegion] = self._rdma_sniffer.get_mrs_by_pdn(
            pd_entity
        )
        for mr in mr_neighbors:
            neighbors.append(mr)
            edges.append(
                OwnEdge.create_ensure_unique_id(
                    source_node=pd_entity,
                    target_node=mr,
                )
            )
        device_neighbors: list[RdmaDevice] = self._rdma_sniffer.get_devices_by_pdn(
            pd_entity
        )
        for device_entity in device_neighbors:
            neighbors.append(device_entity)
            edges.append(
                AccessEdge.create_ensure_unique_id(
                    source_node=pd_entity,
                    target_node=device_entity,
                )
            )
        return neighbors, edges

    def _get_qp_neighbors_with_edges(
        self, entity: RdmaLocalQueuePair
    ) -> tuple[list[Entity], list[Edge]]:
        """Find connected QPs.
        Note that QP connection is not directly observable,
        we can only infer potential connections based on QP attributes
        (e.g., same qpn)."""

        neighbors = []
        edges = []
        qpn_manager = QPNManager()
        other = qpn_manager.get_qp_by_qpn(entity.rqpn)
        if other and other.unique_id != entity.unique_id:
            neighbors.append(other)
            edges.append(
                ConnectToEdge.create_ensure_unique_id(
                    source_node=entity,
                    target_node=other,
                )
            )

        return neighbors, edges

    def _get_device_neighbors_with_edges(
        self, entity: RdmaDevice
    ) -> tuple[list[Entity], list[Edge]]:
        neighbors = []
        edges = []
        statistic: RdmaStatisticPerSecond = self._rdma_sniffer.get_statistic_by_device(
            entity
        )
        if statistic:
            neighbors.append(statistic)
            edges.append(
                HasAttributeEdge(  # not unique
                    source_node=entity,
                    target_node=statistic,
                )
            )

        return neighbors, edges


__all__ = ["RDMACollector"]

if __name__ == "__main__":
    from argparse import ArgumentParser

    collector = RDMACollector()
    collector.start()
    seed_graph = collector._get_seed_graph()

    collected: Graph = collector.expand_since_graph(seed_graph)

    LOGGER.info(f"Collected RDMA topology graph: {collected}")
