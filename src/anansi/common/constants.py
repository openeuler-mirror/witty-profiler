"""Global constants for the Anansi topology collection framework.

Defines immutable constants for entity namespaces, connection types,
and other configuration values used throughout the codebase.

Constants:
    - CONNECTION_TYPE_TCP: TCP socket identifier
    - CONNECTION_TYPE_UDP: UDP socket identifier
    - DEFAULT_NAMESPACE: Default entity namespace when none is active

Default Namespace:
    When EntityNameSpace context is not set, entities use DEFAULT_NAMESPACE ("local")
    to scope their global IDs.
"""

import os
import tempfile
from typing import Final, Literal

CONNECTION_TYPE_TCP: Final[str] = "TCP"
CONNECTION_TYPE_UDP: Final[str] = "UDP"


DEFAULT_NAMESPACE: Final[str] = "local"

PKG_ANANSI_PATH: Final[str] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)


def _get_anansi_lock_dir() -> str:
    """Get the platform-appropriate directory for Anansi lock files.

    Returns:
        Path to the Anansi lock directory (e.g., /tmp/anansi on Unix)
    """
    temp_dir = tempfile.gettempdir()
    lock_dir = os.path.join(temp_dir, "anansi")
    os.makedirs(lock_dir, exist_ok=True)
    return lock_dir


class AnansiServerConstants:
    """Container for Anansi HTTP server constants.

    Grouped to keep server-related defaults editable in a single place.
    Uses UPPER_CASE naming per PEP 8 conventions for module-level constants.
    """

    # Default binding
    DEFAULT_HOST: Final[str] = "0.0.0.0"
    DEFAULT_PORT: Final[int] = 18090

    # HTTP API metadata
    API_TITLE: Final[str] = "Anansi Topology API"
    API_DESCRIPTION: Final[str] = "REST API for querying system topology graphs"
    API_VERSION: Final[str] = "0.1.0"
    HELP_HEADER: Final[str] = "Anansi Topology Server - Help\nUsage:\n"

    # Route paths
    ROUTE_ROOT: Final[str] = "/"
    ROUTE_HELP: Final[str] = "/help"
    ROUTE_GRAPH: Final[str] = "/graph"
    ROUTE_COMPRESSED_GRAPH: Final[str] = "/compressed_graph"
    ROUTE_STATUS: Final[str] = "/status"
    ROUTE_CONTROL_START: Final[str] = "/control/start"
    ROUTE_CONTROL_STOP: Final[str] = "/control/stop"
    ROUTE_CONTROL_TRIGGER: Final[str] = "/control/trigger"
    ROUTE_CONTROL_CLEAR: Final[str] = "/control/clear"
    ROUTE_SUBSCRIBER: Final[str] = "/subscriber"
    ROUTE_SUBSCRIBER_NAME: Final[str] = "/subscriber/{name}"
    ROUTE_SUBSCRIBERS: Final[str] = "/subscribers"

    REMOTE_QUERY_MIN_INTERVAL_BY_SECOND: Final[float] = 1.0


class SocketMonitorConstants:
    @staticmethod
    def LOCK_FILE() -> str:
        """Get the lock file path for socket monitor."""
        return os.path.join(_get_anansi_lock_dir(), "anansi_socket_monitor.lock")


class AnansiProcessConstants:
    @staticmethod
    def LOCK_FILE() -> str:
        """Get the lock file path for Anansi process."""
        return os.path.join(_get_anansi_lock_dir(), "anansi_instance.lock")


class CacheMonitorConstants:
    @staticmethod
    def LOCK_FILE() -> str:
        """Get the lock file path for cache monitor."""
        return os.path.join(_get_anansi_lock_dir(), "anansi_cache_monitor.lock")


class SchedMonitorConstants:
    @staticmethod
    def LOCK_FILE() -> str:
        """Get the lock file path for sched monitor."""
        return os.path.join(_get_anansi_lock_dir(), "anansi_sched_monitor.lock")


class SocketSnifferConstants:
    SOCKET_SNIFFER_MSG_MSGSPEC = "msgspec"
    SOCKET_SNIFFER_MSG_CSV = "csv"


class CacheSnifferConstants:
    CACHE_SNIFFER_MSG_MSGSPEC = "msgspec"
    CACHE_SNIFFER_MSG_CSV = "csv"


class RDMASnifferConstants:
    RDMA_SNIFFER_MSG_MSGSPEC = "msgspec"
    RDMA_SNIFFER_MSG_CSV = "csv"


class CacheMonitorColumn:
    """Columns in the cache monitor dataframe."""

    CPU: Final[str] = "cpu"
    TGID: Final[str] = "tgid"
    PID: Final[str] = "pid"
    TOTAL: Final[str] = "total"
    L1I: Final[str] = "l1i"
    LLC: Final[str] = "llc"
    WINDOW_START_NS: Final[str] = "window_start_ns"
    WINDOW_END_NS: Final[str] = "window_end_ns"

    @staticmethod
    def columns() -> list[str]:
        """Get list of all cache monitor dataframe columns."""
        return [
            CacheMonitorColumn.CPU,
            CacheMonitorColumn.TGID,
            CacheMonitorColumn.PID,
            CacheMonitorColumn.TOTAL,
            CacheMonitorColumn.L1I,
            CacheMonitorColumn.LLC,
            CacheMonitorColumn.WINDOW_START_NS,
            CacheMonitorColumn.WINDOW_END_NS,
        ]


class SchedMonitorColumn:
    """Columns in the sched monitor dataframe."""

    PID: Final[str] = "pid"
    TGID: Final[str] = "tgid"
    CPU: Final[str] = "cpu"
    TIME_NS: Final[str] = "time"
    WINDOW_START_NS: Final[str] = "window_start_ns"
    WINDOW_END_NS: Final[str] = "window_end_ns"

    @staticmethod
    def columns() -> list[str]:
        """Get list of all sched monitor dataframe columns."""
        return [
            SchedMonitorColumn.PID,
            SchedMonitorColumn.TGID,
            SchedMonitorColumn.CPU,
            SchedMonitorColumn.TIME_NS,
            SchedMonitorColumn.WINDOW_START_NS,
            SchedMonitorColumn.WINDOW_END_NS,
        ]


class TimeConstants:
    SECOND2SEC: Final[float] = 1.0
    SEC2MILLISEC: Final[float] = 1e3
    SEC2MICROSEC: Final[float] = 1e6
    SEC2NANOSEC: Final[float] = 1e9


class ProcConstants:
    CPUS_ALLOWED_LIST: Final[str] = "Cpus_allowed_list"
    CPUS_PREFERRED_LIST: Final[str] = "Cpus_preferred_list"
    MEMS_ALLOWED_LIST: Final[str] = "Mems_allowed_list"
    VOLUNTARY_CTX_SWITCHES: Final[str] = "voluntary_ctxt_switches"
    NONVOLUNTARY_CTX_SWITCHES: Final[str] = "nonvoluntary_ctxt_switches"


class HCCSEventType:
    """HCCS event type enum values matching pmu_common.h hccs_event_type."""
    EVENT_DDR: Final[int] = 0
    EVENT_HHA: Final[int] = 1
    EVENT_L3C: Final[int] = 2
    EVENT_PA: Final[int] = 3


class HCCSDDRConstants:
    """DDR PMU event codes from hisi_pmu_events.h."""
    HISI_DDRC_FLUX_WR: Final[int] = 0x83
    HISI_DDRC_FLUX_RD: Final[int] = 0x84
    HISI_DDR_BYTES_PER_COUNT: Final[int] = 32


class HCCSHHAConstants:
    """HHA PMU event codes from hisi_pmu_events.h."""
    HISI_HHA_RX_OPS_NUM: Final[int] = 0x00
    HISI_HHA_RX_OUTER: Final[int] = 0x01
    HISI_HHA_RX_SCCL: Final[int] = 0x02
    HISI_HHA_RD_DDR_64B: Final[int] = 0x1C
    HISI_HHA_WR_DDR_64B: Final[int] = 0x1D
    HISI_HHA_RD_DDR_128B: Final[int] = 0x1E
    HISI_HHA_WR_DDR_128B: Final[int] = 0x1F
    HISI_HHA_64B_ACCESS_SIZE: Final[int] = 64
    HISI_HHA_128B_ACCESS_SIZE: Final[int] = 128


class HCCSL3CConstants:
    """L3C PMU event codes from hisi_pmu_events.h."""
    HISI_L3C_RD_CPIPE: Final[int] = 0x00
    HISI_L3C_WR_CPIPE: Final[int] = 0x01
    HISI_L3C_RD_HIT_CPIPE: Final[int] = 0x02
    HISI_L3C_WR_HIT_CPIPE: Final[int] = 0x03
    HISI_L3C_RD_SPIPE: Final[int] = 0x20
    HISI_L3C_WR_SPIPE: Final[int] = 0x21
    HISI_L3C_RD_HIT_SPIPE: Final[int] = 0x22
    HISI_L3C_WR_HIT_SPIPE: Final[int] = 0x23
    HISI_L3C_BACK_INV_NUM: Final[int] = 0x48
    HISI_L3C_RETRY_REQ: Final[int] = 0xB8


class HCCSPAConstants:
    """PA (Port Agent) PMU event codes from hisi_pmu_events.h."""
    HISI_PA_RING2PA_LINK0: Final[int] = 0x40
    HISI_PA_RING2PA_LINK1: Final[int] = 0x44
    HISI_PA_RING2PA_LINK2: Final[int] = 0x48
    HISI_PA_RING2PA_LINK3: Final[int] = 0x4C
    HISI_PA_PA2RING_LINK0: Final[int] = 0x50
    HISI_PA_PA2RING_LINK1: Final[int] = 0x54
    HISI_PA_PA2RING_LINK2: Final[int] = 0x58
    HISI_PA_PA2RING_LINK3: Final[int] = 0x5C
    HISI_PA_CYCLES: Final[int] = 0x78
    HISI_PA_BW_FACTOR: Final[int] = 30


class HCCSMonitorConstants:
    """HCCS Monitor output style constants."""
    OUTPUT_STYLE_CSV: Final[str] = "csv"
    OUTPUT_STYLE_MSGSPEC: Final[str] = "msgspec"
