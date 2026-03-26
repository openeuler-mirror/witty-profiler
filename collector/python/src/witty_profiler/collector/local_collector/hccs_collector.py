"""Collector for HCCS bandwidth topology.

Simplified collector that delegates to HCCSSniffer for data queries
and only handles Edge generation.

Architecture:
    HCCSMonitor (subprocess management)
        │
        ▼
    HCCSSniffer (bandwidth calculation)
        │
        ▼
    HCCSCollector (Edge generation)
"""

from typing import Tuple

from witty_profiler.collector.local_collector.local_collector import LocalCollector
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.edge.cpu.hccs_edge import (
    DDRBandwidthEdge,
    DDRBandwidthInfo,
    HCCSBandwidthEdge,
    HCCSBandwidthInfo,
    HHABandwidthEdge,
    HHABandwidthInfo,
    L3CBandwidthEdge,
    L3CBandwidthInfo,
    PABandwidthEdge,
    PABandwidthInfo,
)
from witty_profiler.edge.cpu.hccs_sniffer import HCCSBandwidthSnapshot, HCCSSniffer, get_hccs_sniffer
from witty_profiler.edge.cpu.numa_deployment import StaticNumaDeployment
from witty_profiler.edge.edge import Edge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity import NumaEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class HCCSCollector(LocalCollector):
    """Collector for HCCS bandwidth topology.

    Delegates data collection to HCCSSniffer and only handles
    Edge generation for the topology graph.
    """

    def __init__(self):
        self._sniffer: HCCSSniffer = get_hccs_sniffer()
        self._deployment = StaticNumaDeployment()
        self._config = GlobalConfigManager().get_config().collector_config.hccs_collector_config

    def start(self):
        """Start the collector."""
        self._sniffer.start()

    def stop(self):
        """Stop the collector."""
        self._sniffer.stop()

    def clear(self):
        """Clear internal state."""
        self._sniffer.clear()

    def _get_seed_graph(self) -> Graph:
        """Get seed graph from NUMA deployment."""
        seed_nodes = list(self._deployment.numa_nodes.values())
        return Graph(nodes=seed_nodes, edges=[])

    def supported_source_node_type(self) -> set[type]:
        return {NumaEntity}

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[list[Entity], list[Edge]]:
        """Get neighbors and edges for a NUMA entity."""
        if not isinstance(entity, NumaEntity):
            return [], []

        snapshot = self._sniffer.query_bandwidth(entity.numa_id)
        if snapshot is None:
            return [], []

        edges = self._build_edges(entity, snapshot)
        return [], edges

    def _build_edges(
        self,
        entity: NumaEntity,
        snapshot: HCCSBandwidthSnapshot,
    ) -> list[Edge]:
        """Build Edge objects from bandwidth snapshot."""
        edges = []

        if self._config.enable_ddr_bandwidth:
            if snapshot.ddr_total_bw > 0:
                edges.append(DDRBandwidthEdge(
                    source_node=entity,
                    target_node=entity,
                    bandwidth_info=DDRBandwidthInfo(
                        read_bw=snapshot.ddr_read_bw,
                        write_bw=snapshot.ddr_write_bw,
                        total_bw=snapshot.ddr_total_bw,
                        timestamp=snapshot.timestamp,
                    ),
                ))

        if self._config.enable_hha_bandwidth:
            if snapshot.hha_total_ops > 0:
                edges.append(HHABandwidthEdge(
                    source_node=entity,
                    target_node=entity,
                    bandwidth_info=HHABandwidthInfo(
                        total_ops=snapshot.hha_total_ops,
                        cross_socket_ops=snapshot.hha_cross_socket_ops,
                        cross_die_ops=snapshot.hha_cross_die_ops,
                        inner_die_ops=snapshot.hha_inner_die_ops,
                        read_ddr_bw=snapshot.hha_ddr_read_bw,
                        write_ddr_bw=snapshot.hha_ddr_write_bw,
                        total_ddr_bw=snapshot.hha_ddr_total_bw,
                        timestamp=snapshot.timestamp,
                    ),
                ))

                if snapshot.hha_cross_socket_ops > 0:
                    edges.append(HCCSBandwidthEdge(
                        source_node=entity,
                        target_node=entity,
                        bandwidth_info=HCCSBandwidthInfo(
                            cross_socket_ops=snapshot.hha_cross_socket_ops,
                            cross_die_ops=snapshot.hha_cross_die_ops,
                            inner_die_ops=snapshot.hha_inner_die_ops,
                            total_ops=snapshot.hha_total_ops,
                            timestamp=snapshot.timestamp,
                        ),
                    ))

        if self._config.enable_l3c_bandwidth:
            if snapshot.l3c_read_cpipe > 0 or snapshot.l3c_write_cpipe > 0:
                edges.append(L3CBandwidthEdge(
                    source_node=entity,
                    target_node=entity,
                    bandwidth_info=L3CBandwidthInfo(
                        read_cpipe=snapshot.l3c_read_cpipe,
                        write_cpipe=snapshot.l3c_write_cpipe,
                        read_cpipe_hit=snapshot.l3c_read_cpipe_hit,
                        write_cpipe_hit=snapshot.l3c_write_cpipe_hit,
                        read_spipe=snapshot.l3c_read_spipe,
                        write_spipe=snapshot.l3c_write_spipe,
                        read_spipe_hit=snapshot.l3c_read_spipe_hit,
                        write_spipe_hit=snapshot.l3c_write_spipe_hit,
                        back_inv_ops=snapshot.l3c_back_inv_ops,
                        retry_req_ops=snapshot.l3c_retry_req_ops,
                        timestamp=snapshot.timestamp,
                    ),
                ))

        if self._config.enable_pa_bandwidth:
            if snapshot.pa_ring2pa_total > 0 or snapshot.pa_pa2ring_total > 0:
                edges.append(PABandwidthEdge(
                    source_node=entity,
                    target_node=entity,
                    bandwidth_info=PABandwidthInfo(
                        ring2pa_total=snapshot.pa_ring2pa_total,
                        pa2ring_total=snapshot.pa_pa2ring_total,
                        ring2pa_link0=snapshot.pa_ring2pa_link0,
                        ring2pa_link1=snapshot.pa_ring2pa_link1,
                        ring2pa_link2=snapshot.pa_ring2pa_link2,
                        ring2pa_link3=snapshot.pa_ring2pa_link3,
                        pa2ring_link0=snapshot.pa_pa2ring_link0,
                        pa2ring_link1=snapshot.pa_pa2ring_link1,
                        pa2ring_link2=snapshot.pa_pa2ring_link2,
                        pa2ring_link3=snapshot.pa_pa2ring_link3,
                        timestamp=snapshot.timestamp,
                    ),
                ))

        return edges


__all__ = ["HCCSCollector"]
