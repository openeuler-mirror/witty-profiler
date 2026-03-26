"""HCCS sniffer for bandwidth calculation and query APIs.

Architecture:
    HCCSMonitor
        │
        │ CountersDict subscription
        ▼
    HCCSSniffer (this module)
        │
        │ BandwidthSnapshot query APIs
        ▼
    HCCSCollector

Features:
    - Subscribes to HCCSMonitor for counter updates
    - Calculates bandwidth metrics from raw counters
    - Provides query APIs for bandwidth data
    - Thread-safe data access

Usage:
    ```python
    sniffer = get_hccs_sniffer()
    sniffer.start()

    # Query bandwidth for a NUMA node
    snapshot = sniffer.query_bandwidth(numa_id=0)

    # Query all NUMA nodes
    all_bw = sniffer.query_all_bandwidth()

    sniffer.stop()
    ```
"""

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from anansi.common.constants import (
    HCCSDDRConstants,
    HCCSEventType,
    HCCSHHAConstants,
    HCCSL3CConstants,
    HCCSPAConstants,
)
from anansi.common.logging import get_logger
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.edge.cpu.hccs_monitor import (
    CountersDict,
    get_hccs_monitor,
)
from anansi.edge.cpu.numa_deployment import StaticNumaDeployment

LOGGER = get_logger(__name__)

EVENT_DDR = HCCSEventType.EVENT_DDR
EVENT_HHA = HCCSEventType.EVENT_HHA
EVENT_L3C = HCCSEventType.EVENT_L3C
EVENT_PA = HCCSEventType.EVENT_PA

HISI_DDR_BYTES_PER_COUNT = HCCSDDRConstants.HISI_DDR_BYTES_PER_COUNT
HISI_DDRC_FLUX_WR = HCCSDDRConstants.HISI_DDRC_FLUX_WR
HISI_DDRC_FLUX_RD = HCCSDDRConstants.HISI_DDRC_FLUX_RD

HISI_HHA_64B_ACCESS_SIZE = HCCSHHAConstants.HISI_HHA_64B_ACCESS_SIZE
HISI_HHA_128B_ACCESS_SIZE = HCCSHHAConstants.HISI_HHA_128B_ACCESS_SIZE
HISI_HHA_RX_OPS_NUM = HCCSHHAConstants.HISI_HHA_RX_OPS_NUM
HISI_HHA_RX_OUTER = HCCSHHAConstants.HISI_HHA_RX_OUTER
HISI_HHA_RX_SCCL = HCCSHHAConstants.HISI_HHA_RX_SCCL
HISI_HHA_RD_DDR_64B = HCCSHHAConstants.HISI_HHA_RD_DDR_64B
HISI_HHA_WR_DDR_64B = HCCSHHAConstants.HISI_HHA_WR_DDR_64B
HISI_HHA_RD_DDR_128B = HCCSHHAConstants.HISI_HHA_RD_DDR_128B
HISI_HHA_WR_DDR_128B = HCCSHHAConstants.HISI_HHA_WR_DDR_128B

HISI_L3C_RD_CPIPE = HCCSL3CConstants.HISI_L3C_RD_CPIPE
HISI_L3C_WR_CPIPE = HCCSL3CConstants.HISI_L3C_WR_CPIPE
HISI_L3C_RD_HIT_CPIPE = HCCSL3CConstants.HISI_L3C_RD_HIT_CPIPE
HISI_L3C_WR_HIT_CPIPE = HCCSL3CConstants.HISI_L3C_WR_HIT_CPIPE
HISI_L3C_RD_SPIPE = HCCSL3CConstants.HISI_L3C_RD_SPIPE
HISI_L3C_WR_SPIPE = HCCSL3CConstants.HISI_L3C_WR_SPIPE
HISI_L3C_RD_HIT_SPIPE = HCCSL3CConstants.HISI_L3C_RD_HIT_SPIPE
HISI_L3C_WR_HIT_SPIPE = HCCSL3CConstants.HISI_L3C_WR_HIT_SPIPE
HISI_L3C_BACK_INV_NUM = HCCSL3CConstants.HISI_L3C_BACK_INV_NUM
HISI_L3C_RETRY_REQ = HCCSL3CConstants.HISI_L3C_RETRY_REQ

HISI_PA_BW_FACTOR = HCCSPAConstants.HISI_PA_BW_FACTOR
HISI_PA_RING2PA_LINK0 = HCCSPAConstants.HISI_PA_RING2PA_LINK0
HISI_PA_RING2PA_LINK1 = HCCSPAConstants.HISI_PA_RING2PA_LINK1
HISI_PA_RING2PA_LINK2 = HCCSPAConstants.HISI_PA_RING2PA_LINK2
HISI_PA_RING2PA_LINK3 = HCCSPAConstants.HISI_PA_RING2PA_LINK3
HISI_PA_PA2RING_LINK0 = HCCSPAConstants.HISI_PA_PA2RING_LINK0
HISI_PA_PA2RING_LINK1 = HCCSPAConstants.HISI_PA_PA2RING_LINK1
HISI_PA_PA2RING_LINK2 = HCCSPAConstants.HISI_PA_PA2RING_LINK2
HISI_PA_PA2RING_LINK3 = HCCSPAConstants.HISI_PA_PA2RING_LINK3
HISI_PA_CYCLES = HCCSPAConstants.HISI_PA_CYCLES


@dataclass
class HCCSBandwidthSnapshot:
    """Complete bandwidth snapshot for a NUMA node."""
    numa_id: int
    sccl_id: int
    timestamp: float

    ddr_read_bw: float = 0.0
    ddr_write_bw: float = 0.0
    ddr_total_bw: float = 0.0

    hha_total_ops: float = 0.0
    hha_cross_socket_ops: float = 0.0
    hha_cross_die_ops: float = 0.0
    hha_inner_die_ops: float = 0.0
    hha_ddr_read_bw: float = 0.0
    hha_ddr_write_bw: float = 0.0
    hha_ddr_total_bw: float = 0.0

    l3c_read_cpipe: float = 0.0
    l3c_write_cpipe: float = 0.0
    l3c_read_cpipe_hit: float = 0.0
    l3c_write_cpipe_hit: float = 0.0
    l3c_read_spipe: float = 0.0
    l3c_write_spipe: float = 0.0
    l3c_read_spipe_hit: float = 0.0
    l3c_write_spipe_hit: float = 0.0
    l3c_back_inv_ops: float = 0.0
    l3c_retry_req_ops: float = 0.0

    pa_ring2pa_total: float = 0.0
    pa_pa2ring_total: float = 0.0
    pa_ring2pa_link0: float = 0.0
    pa_ring2pa_link1: float = 0.0
    pa_ring2pa_link2: float = 0.0
    pa_ring2pa_link3: float = 0.0
    pa_pa2ring_link0: float = 0.0
    pa_pa2ring_link1: float = 0.0
    pa_pa2ring_link2: float = 0.0
    pa_pa2ring_link3: float = 0.0

    hccs_cross_socket_bw: float = 0.0


def _sccl_to_numa_ids(deployment: StaticNumaDeployment) -> dict[int, list[int]]:
    """Map SCCL ID to NUMA node IDs."""
    numa_nodes = deployment.numa_nodes
    if not numa_nodes:
        return {}

    numa_ids = sorted(numa_nodes.keys())
    if len(numa_ids) <= 1:
        return {0: numa_ids}

    visited = set()
    clusters: list[list[int]] = []
    for nid in numa_ids:
        if nid in visited:
            continue
        cluster = [nid]
        visited.add(nid)
        distances = deployment.numa_distances.get(nid, {})
        for other_nid in numa_ids:
            if other_nid in visited:
                continue
            if distances.get(other_nid, 999) <= 15:
                cluster.append(other_nid)
                visited.add(other_nid)
        clusters.append(sorted(cluster))

    clusters.sort(key=lambda c: c[0])
    return {sccl_id: nids for sccl_id, nids in enumerate(clusters)}


class HCCSSniffer:
    """Sniffer for HCCS bandwidth data.

    Subscribes to HCCSMonitor and provides query APIs for bandwidth data.
    """

    def __init__(self):
        self._monitor = get_hccs_monitor()
        self._deployment = StaticNumaDeployment()
        self._sccl_to_numas = _sccl_to_numa_ids(self._deployment)
        self._numa_to_sccl = self._build_numa_to_sccl_map()

        self._counters: CountersDict = {}
        self._counters_lock = threading.RLock()

        self._subscription_name: Optional[str] = None
        self._started = False

        mngr = GlobalConfigManager.get_instance()
        self._config = mngr.get_config().collector_config.hccs_collector_config

    def _build_numa_to_sccl_map(self) -> dict[int, int]:
        """Build mapping from NUMA ID to SCCL ID."""
        result = {}
        for sccl_id, numa_ids in self._sccl_to_numas.items():
            for numa_id in numa_ids:
                result[numa_id] = sccl_id
        return result

    def start(self) -> bool:
        """Start the sniffer by subscribing to monitor."""
        if self._started:
            return True

        self._subscription_name = f"hccs_sniffer_{uuid.uuid4().hex[:8]}"
        self._monitor.register_subscriber(
            self._subscription_name,
            self._on_counters_update
        )
        self._started = True
        LOGGER.info("HCCSSniffer started with subscription '%s'", self._subscription_name)
        return True

    def stop(self):
        """Stop the sniffer."""
        if self._subscription_name:
            self._monitor.unregister_subscriber(self._subscription_name)
            self._subscription_name = None
        self._started = False
        LOGGER.info("HCCSSniffer stopped")

    def clear(self):
        """Clear cached counters."""
        with self._counters_lock:
            self._counters.clear()

    def _on_counters_update(self, counters: CountersDict):
        """Callback for monitor counter updates."""
        with self._counters_lock:
            self._counters = counters

    def query_bandwidth(self, numa_id: int) -> Optional[HCCSBandwidthSnapshot]:
        """Query bandwidth for a specific NUMA node."""
        sccl_id = self._numa_to_sccl.get(numa_id)
        if sccl_id is None:
            return None

        with self._counters_lock:
            counters = dict(self._counters)

        return self._calculate_bandwidth(numa_id, sccl_id, counters)

    def query_all_bandwidth(self) -> dict[int, HCCSBandwidthSnapshot]:
        """Query bandwidth for all NUMA nodes."""
        result = {}
        for numa_id in self._numa_to_sccl:
            snapshot = self.query_bandwidth(numa_id)
            if snapshot:
                result[numa_id] = snapshot
        return result

    def _get_counter(
        self,
        sccl_id: int,
        event_type: int,
        event_code: int,
        counters: CountersDict,
    ) -> tuple[int, float]:
        """Get counter value for a specific event."""
        return counters.get((sccl_id, event_type, event_code), (0, 1.0))

    def _calculate_bandwidth(
        self,
        numa_id: int,
        sccl_id: int,
        counters: CountersDict,
    ) -> HCCSBandwidthSnapshot:
        """Calculate bandwidth from counters."""
        snapshot = HCCSBandwidthSnapshot(
            numa_id=numa_id,
            sccl_id=sccl_id,
            timestamp=time.time(),
        )

        if self._config.enable_ddr_bandwidth:
            self._calc_ddr_bandwidth(sccl_id, counters, snapshot)

        if self._config.enable_hha_bandwidth:
            self._calc_hha_bandwidth(sccl_id, counters, snapshot)

        if self._config.enable_l3c_bandwidth:
            self._calc_l3c_bandwidth(sccl_id, counters, snapshot)

        if self._config.enable_pa_bandwidth:
            self._calc_pa_bandwidth(sccl_id, counters, snapshot)

        return snapshot

    def _calc_ddr_bandwidth(
        self,
        sccl_id: int,
        counters: CountersDict,
        snapshot: HCCSBandwidthSnapshot,
    ):
        """Calculate DDR bandwidth."""
        wr_count, wr_interval = self._get_counter(
            sccl_id, EVENT_DDR, HISI_DDRC_FLUX_WR, counters
        )
        rd_count, rd_interval = self._get_counter(
            sccl_id, EVENT_DDR, HISI_DDRC_FLUX_RD, counters
        )

        snapshot.ddr_write_bw = wr_count * HISI_DDR_BYTES_PER_COUNT / wr_interval / 1e9
        snapshot.ddr_read_bw = rd_count * HISI_DDR_BYTES_PER_COUNT / rd_interval / 1e9
        snapshot.ddr_total_bw = snapshot.ddr_read_bw + snapshot.ddr_write_bw

    def _calc_hha_bandwidth(
        self,
        sccl_id: int,
        counters: CountersDict,
        snapshot: HCCSBandwidthSnapshot,
    ):
        """Calculate HHA bandwidth."""
        total_count, total_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_RX_OPS_NUM, counters
        )
        outer_count, outer_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_RX_OUTER, counters
        )
        sccl_count, sccl_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_RX_SCCL, counters
        )
        rd64_count, rd64_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_RD_DDR_64B, counters
        )
        wr64_count, wr64_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_WR_DDR_64B, counters
        )
        rd128_count, rd128_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_RD_DDR_128B, counters
        )
        wr128_count, wr128_iv = self._get_counter(
            sccl_id, EVENT_HHA, HISI_HHA_WR_DDR_128B, counters
        )

        if total_count == 0:
            return

        snapshot.hha_total_ops = total_count / total_iv / 1e9
        snapshot.hha_cross_socket_ops = outer_count / outer_iv / 1e9
        snapshot.hha_cross_die_ops = sccl_count / sccl_iv / 1e9
        snapshot.hha_inner_die_ops = max(
            0.0,
            snapshot.hha_total_ops - snapshot.hha_cross_socket_ops - snapshot.hha_cross_die_ops
        )

        snapshot.hha_ddr_read_bw = (
            rd64_count * HISI_HHA_64B_ACCESS_SIZE / rd64_iv
            + rd128_count * HISI_HHA_128B_ACCESS_SIZE / rd128_iv
        ) / 1e9
        snapshot.hha_ddr_write_bw = (
            wr64_count * HISI_HHA_64B_ACCESS_SIZE / wr64_iv
            + wr128_count * HISI_HHA_128B_ACCESS_SIZE / wr128_iv
        ) / 1e9
        snapshot.hha_ddr_total_bw = snapshot.hha_ddr_read_bw + snapshot.hha_ddr_write_bw

        snapshot.hccs_cross_socket_bw = snapshot.hha_cross_socket_ops

    def _calc_l3c_bandwidth(
        self,
        sccl_id: int,
        counters: CountersDict,
        snapshot: HCCSBandwidthSnapshot,
    ):
        """Calculate L3C bandwidth."""
        get = lambda code: self._get_counter(sccl_id, EVENT_L3C, code, counters)

        rd_cpipe, rd_cpipe_iv = get(HISI_L3C_RD_CPIPE)
        wr_cpipe, wr_cpipe_iv = get(HISI_L3C_WR_CPIPE)
        rd_hit_cpipe, rd_hit_cpipe_iv = get(HISI_L3C_RD_HIT_CPIPE)
        wr_hit_cpipe, wr_hit_cpipe_iv = get(HISI_L3C_WR_HIT_CPIPE)
        rd_spipe, rd_spipe_iv = get(HISI_L3C_RD_SPIPE)
        wr_spipe, wr_spipe_iv = get(HISI_L3C_WR_SPIPE)
        rd_hit_spipe, rd_hit_spipe_iv = get(HISI_L3C_RD_HIT_SPIPE)
        wr_hit_spipe, wr_hit_spipe_iv = get(HISI_L3C_WR_HIT_SPIPE)
        back_inv, back_inv_iv = get(HISI_L3C_BACK_INV_NUM)
        retry_req, retry_req_iv = get(HISI_L3C_RETRY_REQ)

        if rd_cpipe == 0 and wr_cpipe == 0:
            return

        snapshot.l3c_read_cpipe = rd_cpipe / rd_cpipe_iv / 1e9
        snapshot.l3c_write_cpipe = wr_cpipe / wr_cpipe_iv / 1e9
        snapshot.l3c_read_cpipe_hit = rd_hit_cpipe / rd_hit_cpipe_iv / 1e9
        snapshot.l3c_write_cpipe_hit = wr_hit_cpipe / wr_hit_cpipe_iv / 1e9
        snapshot.l3c_read_spipe = rd_spipe / rd_spipe_iv / 1e9
        snapshot.l3c_write_spipe = wr_spipe / wr_spipe_iv / 1e9
        snapshot.l3c_read_spipe_hit = rd_hit_spipe / rd_hit_spipe_iv / 1e9
        snapshot.l3c_write_spipe_hit = wr_hit_spipe / wr_hit_spipe_iv / 1e9
        snapshot.l3c_back_inv_ops = back_inv / back_inv_iv / 1e9
        snapshot.l3c_retry_req_ops = retry_req / retry_req_iv / 1e9

    def _calc_pa_bandwidth(
        self,
        sccl_id: int,
        counters: CountersDict,
        snapshot: HCCSBandwidthSnapshot,
    ):
        """Calculate PA bandwidth."""
        get = lambda code: self._get_counter(sccl_id, EVENT_PA, code, counters)

        r2p_l0, r2p_l0_iv = get(HISI_PA_RING2PA_LINK0)
        r2p_l1, r2p_l1_iv = get(HISI_PA_RING2PA_LINK1)
        r2p_l2, r2p_l2_iv = get(HISI_PA_RING2PA_LINK2)
        r2p_l3, r2p_l3_iv = get(HISI_PA_RING2PA_LINK3)
        p2r_l0, p2r_l0_iv = get(HISI_PA_PA2RING_LINK0)
        p2r_l1, p2r_l1_iv = get(HISI_PA_PA2RING_LINK1)
        p2r_l2, p2r_l2_iv = get(HISI_PA_PA2RING_LINK2)
        p2r_l3, p2r_l3_iv = get(HISI_PA_PA2RING_LINK3)
        cycles, cycles_iv = get(HISI_PA_CYCLES)

        if cycles == 0:
            return

        cycle_rate = cycles / cycles_iv

        def link_bw(flit_count: int, flit_iv: float) -> float:
            flit_rate = flit_count / flit_iv
            return (flit_rate / cycle_rate) * HISI_PA_BW_FACTOR if cycle_rate > 0 else 0.0

        snapshot.pa_ring2pa_link0 = link_bw(r2p_l0, r2p_l0_iv)
        snapshot.pa_ring2pa_link1 = link_bw(r2p_l1, r2p_l1_iv)
        snapshot.pa_ring2pa_link2 = link_bw(r2p_l2, r2p_l2_iv)
        snapshot.pa_ring2pa_link3 = link_bw(r2p_l3, r2p_l3_iv)
        snapshot.pa_pa2ring_link0 = link_bw(p2r_l0, p2r_l0_iv)
        snapshot.pa_pa2ring_link1 = link_bw(p2r_l1, p2r_l1_iv)
        snapshot.pa_pa2ring_link2 = link_bw(p2r_l2, p2r_l2_iv)
        snapshot.pa_pa2ring_link3 = link_bw(p2r_l3, p2r_l3_iv)

        snapshot.pa_ring2pa_total = (
            snapshot.pa_ring2pa_link0
            + snapshot.pa_ring2pa_link1
            + snapshot.pa_ring2pa_link2
            + snapshot.pa_ring2pa_link3
        )
        snapshot.pa_pa2ring_total = (
            snapshot.pa_pa2ring_link0
            + snapshot.pa_pa2ring_link1
            + snapshot.pa_pa2ring_link2
            + snapshot.pa_pa2ring_link3
        )


def get_hccs_sniffer() -> HCCSSniffer:
    """Get the HCCSSniffer instance."""
    return HCCSSniffer()


__all__ = [
    "HCCSSniffer",
    "HCCSBandwidthSnapshot",
    "get_hccs_sniffer",
]
