"""HCCS (Huawei Cache Coherence System) edge definitions.

Defines edges and data structures for representing HCCS bandwidth
relationships between entities in the topology graph.

Key Components:
    - HCCSStream: Base edge class for HCCS data streams
    - HCCSBandwidthEdge: Edge representing HCCS bandwidth between chips
    - DDRBandwidthEdge: Edge representing DDR memory bandwidth
    - HHABandwidthInfo: Data structure for HHA bandwidth metrics
"""

from dataclasses import dataclass, field

from witty_profiler.edge.edge_category import DataStreamEdge
from witty_profiler.entity.entity_base import Entity


@dataclass
class HCCSBandwidthInfo:
    """HCCS bandwidth information for cross-chip communication.
    
    Attributes:
        cross_socket_ops: Operations from other sockets (Gops/s) - HCCS traffic
        cross_die_ops: Operations from other dies (Gops/s)
        inner_die_ops: Operations within same die (Gops/s)
        total_ops: Total operations (Gops/s)
        timestamp: Snapshot timestamp
    """
    cross_socket_ops: float = 0.0
    cross_die_ops: float = 0.0
    inner_die_ops: float = 0.0
    total_ops: float = 0.0
    timestamp: float = 0.0
    
    def __post_init__(self):
        pass
    
    @property
    def hccs_bandwidth_gbps(self) -> float:
        """Get HCCS cross-socket bandwidth in Gops/s."""
        return self.cross_socket_ops
    
    def __str__(self) -> str:
        return (
            f"[HCCS] cross_socket={self.cross_socket_ops:.3f} Gops/s, "
            f"cross_die={self.cross_die_ops:.3f} Gops/s"
        )


@dataclass
class DDRBandwidthInfo:
    """DDR memory bandwidth information.
    
    Attributes:
        read_bw: Read bandwidth (GB/s)
        write_bw: Write bandwidth (GB/s)
        total_bw: Total bandwidth (GB/s)
        timestamp: Snapshot timestamp
    """
    read_bw: float = 0.0
    write_bw: float = 0.0
    total_bw: float = 0.0
    timestamp: float = 0.0
    
    def __str__(self) -> str:
        return (
            f"[DDR] read={self.read_bw:.3f} GB/s, "
            f"write={self.write_bw:.3f} GB/s, "
            f"total={self.total_bw:.3f} GB/s"
        )


@dataclass
class HHABandwidthInfo:
    """HHA (Hyper Home Agent) bandwidth information.
    
    HHA is the inter-chip interconnect agent in Kunpeng processors.
    """
    total_ops: float = 0.0
    cross_socket_ops: float = 0.0
    cross_die_ops: float = 0.0
    inner_die_ops: float = 0.0
    read_ddr_bw: float = 0.0
    write_ddr_bw: float = 0.0
    total_ddr_bw: float = 0.0
    timestamp: float = 0.0
    
    def __str__(self) -> str:
        return (
            f"[HHA] total={self.total_ops:.3f} Gops/s, "
            f"cross_socket={self.cross_socket_ops:.3f} Gops/s, "
            f"ddr_bw={self.total_ddr_bw:.3f} GB/s"
        )


@dataclass
class L3CBandwidthInfo:
    """L3 cache bandwidth information.

    Attributes:
        read_cpipe: Read operations through CPIPE (Gops/s)
        write_cpipe: Write operations through CPIPE (Gops/s)
        read_cpipe_hit: Read hits through CPIPE (Gops/s)
        write_cpipe_hit: Write hits through CPIPE (Gops/s)
        read_spipe: Read operations through SPIPE (Gops/s)
        write_spipe: Write operations through SPIPE (Gops/s)
        read_spipe_hit: Read hits through SPIPE (Gops/s)
        write_spipe_hit: Write hits through SPIPE (Gops/s)
        back_inv_ops: Back invalidation operations (Gops/s) - measures cache coherence traffic
        retry_req_ops: Retry request operations (Gops/s)
        timestamp: Snapshot timestamp
    """
    read_cpipe: float = 0.0
    write_cpipe: float = 0.0
    read_cpipe_hit: float = 0.0
    write_cpipe_hit: float = 0.0
    read_spipe: float = 0.0
    write_spipe: float = 0.0
    read_spipe_hit: float = 0.0
    write_spipe_hit: float = 0.0
    back_inv_ops: float = 0.0
    retry_req_ops: float = 0.0
    timestamp: float = 0.0

    @property
    def total_hit_rate(self) -> float:
        """Calculate L3 cache hit rate based on CPIPE access and hits."""
        total_access = self.read_cpipe + self.write_cpipe
        if total_access == 0:
            return 0.0
        total_hit = self.read_cpipe_hit + self.write_cpipe_hit
        return total_hit / total_access

    @property
    def total_ops(self) -> float:
        """Total L3 cache operations (Gops/s)."""
        return self.read_cpipe + self.write_cpipe + self.read_spipe + self.write_spipe

    def __str__(self) -> str:
        return (
            f"[L3C] hit_rate={self.total_hit_rate:.2%}, "
            f"total_ops={self.total_ops:.3f} Gops/s, "
            f"back_inv={self.back_inv_ops:.3f} Gops/s"
        )


@dataclass
class PABandwidthInfo:
    """PA (Port Agent) bandwidth information.
    
    PA handles HCCS link communication.
    """
    ring2pa_total: float = 0.0
    pa2ring_total: float = 0.0
    ring2pa_link0: float = 0.0
    ring2pa_link1: float = 0.0
    ring2pa_link2: float = 0.0
    ring2pa_link3: float = 0.0
    pa2ring_link0: float = 0.0
    pa2ring_link1: float = 0.0
    pa2ring_link2: float = 0.0
    pa2ring_link3: float = 0.0
    timestamp: float = 0.0
    
    @property
    def total_hccs_bw(self) -> float:
        """Get total HCCS link bandwidth."""
        return self.ring2pa_total + self.pa2ring_total
    
    def __str__(self) -> str:
        return (
            f"[PA] ring2pa={self.ring2pa_total:.3f} GB/s, "
            f"pa2ring={self.pa2ring_total:.3f} GB/s"
        )


class HCCSStream(DataStreamEdge):
    """Base edge class for HCCS data streams.
    
    HCCS (Huawei Cache Coherence System) is the inter-chip interconnect
    technology used in Huawei Kunpeng processors. This edge represents
    data streams related to HCCS bandwidth monitoring.
    
    All HCCS-related bandwidth edges should inherit from this class.
    
    Attributes:
        source_node: Source entity (typically NUMA node)
        target_node: Target entity (typically memory/cache resource)
    """
    
    source_node: Entity = field(default_factory=Entity)
    target_node: Entity = field(default_factory=Entity)
    
    def __post_init__(self):
        super().__post_init__()
    
    def __str__(self) -> str:
        return f"{super().__str__()}"


class HCCSBandwidthEdge(HCCSStream):
    """Edge representing HCCS bandwidth between NUMA nodes/chips.
    
    This edge captures the cross-socket communication bandwidth
    measured by HHA (Hyper Home Agent) PMU counters.
    
    Attributes:
        bandwidth_info: HCCS bandwidth information
    """
    
    bandwidth_info: HCCSBandwidthInfo = field(
        default_factory=HCCSBandwidthInfo
    )
    
    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.bandwidth_info, dict):
            self.bandwidth_info = HCCSBandwidthInfo(**self.bandwidth_info)
    
    def __str__(self) -> str:
        return f"{super().__str__()}({self.bandwidth_info})"


class DDRBandwidthEdge(HCCSStream):
    """Edge representing DDR memory bandwidth for a NUMA node.
    
    Attributes:
        bandwidth_info: DDR bandwidth information
    """
    
    bandwidth_info: DDRBandwidthInfo = field(
        default_factory=DDRBandwidthInfo
    )
    
    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.bandwidth_info, dict):
            self.bandwidth_info = DDRBandwidthInfo(**self.bandwidth_info)
    
    def __str__(self) -> str:
        return f"{super().__str__()}({self.bandwidth_info})"


class HHABandwidthEdge(HCCSStream):
    """Edge representing HHA bandwidth for a NUMA node.
    
    Attributes:
        bandwidth_info: HHA bandwidth information
    """
    
    bandwidth_info: HHABandwidthInfo = field(
        default_factory=HHABandwidthInfo
    )
    
    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.bandwidth_info, dict):
            self.bandwidth_info = HHABandwidthInfo(**self.bandwidth_info)
    
    def __str__(self) -> str:
        return f"{super().__str__()}({self.bandwidth_info})"


class L3CBandwidthEdge(HCCSStream):
    """Edge representing L3 cache bandwidth for a NUMA node.
    
    Attributes:
        bandwidth_info: L3C bandwidth information
    """
    
    bandwidth_info: L3CBandwidthInfo = field(
        default_factory=L3CBandwidthInfo
    )
    
    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.bandwidth_info, dict):
            self.bandwidth_info = L3CBandwidthInfo(**self.bandwidth_info)
    
    def __str__(self) -> str:
        return f"{super().__str__()}({self.bandwidth_info})"


class PABandwidthEdge(HCCSStream):
    """Edge representing PA (Port Agent) bandwidth for HCCS links.
    
    Attributes:
        bandwidth_info: PA bandwidth information
    """
    
    bandwidth_info: PABandwidthInfo = field(
        default_factory=PABandwidthInfo
    )
    
    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.bandwidth_info, dict):
            self.bandwidth_info = PABandwidthInfo(**self.bandwidth_info)
    
    def __str__(self) -> str:
        return f"{super().__str__()}({self.bandwidth_info})"


__all__ = [
    "HCCSStream",
    "HCCSBandwidthInfo",
    "DDRBandwidthInfo",
    "HHABandwidthInfo",
    "L3CBandwidthInfo",
    "PABandwidthInfo",
    "HCCSBandwidthEdge",
    "DDRBandwidthEdge",
    "HHABandwidthEdge",
    "L3CBandwidthEdge",
    "PABandwidthEdge",
]
