import os
import threading
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from witty_profiler.common.constants import CONNECTION_TYPE_TCP, CONNECTION_TYPE_UDP
from witty_profiler.common.singleton import Singleton
from witty_profiler.common.str_converter import list_to_range_str, range_str_to_list
from witty_profiler.entity.entity_base import Entity, field


class QPNManager(Singleton):
    """
    Manager for RDMA Queue Pair Numbers (QPNs) to ensure uniqueness across the system.
    """

    qpn2qp: Dict[int, "RdmaQueuePairEndpoint"] = {}

    def __init__(self):
        self._lock = threading.RLock()

    def clear(self):
        with self._lock:
            self.qpn2qp.clear()

    def register_qp(self, qp: "RdmaQueuePairEndpoint") -> bool:
        """
        Register a Queue Pair Endpoint with its QPN. Returns True if registration is successful, False if QPN is already registered.
        """
        with self._lock:
            if qp.qpn in self.qpn2qp:
                return False
            self.qpn2qp[qp.qpn] = qp
        return True

    def get_qp_by_qpn(self, qpn: int) -> Optional["RdmaQueuePairEndpoint"]:
        """
        Get the Queue Pair Endpoint associated with a given QPN. Returns None if not found.
        """
        with self._lock:
            return self.qpn2qp.get(qpn)


class RdmaQueuePairEndpoint(Entity):
    """
    Entity representing a RDMA Queue Pair Endpoint, which can be either local or remote.
    """

    qpn: int = field(default=-1)  # Queue Pair Number (lqpn)

    def __post_init__(self):
        super().__post_init__()
        QPNManager().register_qp(self)

    @property
    def unique_id(self) -> str:
        return f"qpn={self.qpn}"


class RdmaLocalQueuePair(RdmaQueuePairEndpoint):
    """
    Entity representing a RDMA Queue Pair Endpoint
    """

    pid: int = field(default=-1)  # Process ID owning the QP
    pdn: int = field(default=-1)  # Protection Domain Number
    dev: str = field(default="")  # RDMA device name, e.g., "mlx5_0"
    port: int = field(default=-1)  # Port number of the RDMA device
    rqpn: int = field(default=-1)  # Remote Queue Pair Number (if known)

    # other fields can be added as needed
    @property
    def unique_id(self) -> str:
        return f"pid={self.pid},qpn={self.qpn}"


class RdmaProtectionDomain(Entity):
    """
    Entity representing a RDMA Protection Domain
    """

    pdn: int = field(default=-1)  # Protection Domain Number
    pid: int = field(default=-1)  # Process ID owning the PD
    dev: str = field(default="")  # RDMA device name, e.g., "mlx5_0"

    # other fields can be added as needed
    @property
    def unique_id(self) -> str:
        return f"pid={self.pid},pdn={self.pdn}"


class RdmaStatisticPerSecond(Entity):
    dev: str = field(default="")  # RDMA device name, e.g., "mlx5_0"
    port: int = field(default=-1)  # Port number of the RDMA device
    send_pkts: float = field(default=0)
    recv_pkts: float = field(default=0)
    dupl_pkts: float = field(default=0)
    rdma_sends: float = field(default=0)
    rdma_recvs: float = field(default=0)

    def __str__(self) -> str:
        return (
            f"RdmaStatisticPerSecond("
            f"dev={self.dev},"
            f"port={self.port},"
            f"send_pkts={self.send_pkts:03f},"
            f"recv_pkts={self.recv_pkts:03f},"
            f"dupl_pkts={self.dupl_pkts:03f},"
            f"rdma_sends={self.rdma_sends:03f},"
            f"rdma_recvs={self.rdma_recvs:03f})"
        )

    @property
    def unique_id(self) -> str:
        return f"dev={self.dev},port={self.port}"


class RdmaDevice(Entity):
    """
    Entity representing a RDMA Device
    """

    dev: str = field(default="")  # RDMA device name, e.g., "mlx5_0"
    stats: Dict[str, RdmaStatisticPerSecond] = field(
        default_factory=dict
    )  # Keyed by dev/port string, e.g., "mlx5_0/1", "rxe1/1", "hns1/1"

    # other fields can be added as needed

    def __post_init__(self):
        super().__post_init__()
        for k in self.stats:
            if isinstance(self.stats[k], dict):
                self.stats[k] = RdmaStatisticPerSecond(**self.stats[k])

    @property
    def unique_id(self) -> str:
        return f"dev={self.dev}"

    def __str__(
        self,
    ) -> str:  # real-time rendering of stats
        return f"[RDMADevice](dev={self.dev}, stats={self.stats})"


class RdmaMemoryRegion(Entity):
    """
    Entity representing a RDMA Memory Region
    """

    lkey: int = field(default=-1)  # Local Key
    rkey: int = field(default=-1)  # Remote Key
    mrlen: int = field(default=-1)  # Memory Region Length
    pdn: int = field(default=-1)  # Protection Domain Number
    pid: int = field(default=-1)  # Process ID owning the MR

    # other fields can be added as needed

    @property
    def unique_id(self) -> str:
        return f"pid={self.pid},pdn={self.pdn},lkey={self.lkey}"
