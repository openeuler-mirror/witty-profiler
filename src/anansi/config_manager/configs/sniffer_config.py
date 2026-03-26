import os
from dataclasses import dataclass, field
from typing import Optional

from anansi.common.constants import PKG_ANANSI_PATH
from anansi.common.constants import AnansiServerConstants as ASC
from anansi.common.constants import (
    CacheSnifferConstants,
    RDMASnifferConstants,
    SocketSnifferConstants,
)
from anansi.entity.entity_base import Entity


@dataclass
class SocketSnifferConfig:
    socket_sniffer_binary_path: str = field(default=None)
    msg_style: str = field(
        default=SocketSnifferConstants.SOCKET_SNIFFER_MSG_CSV
    )  # csv or msgspec
    monitor_report_maximum_interval_by_second: float = field(default=2.0)

    data_file_path: str = field(default="anansi.socket_sniffer.csv")
    maximum_log_file_size_in_mb: int = field(default=100)
    maximum_rotation_cnt: int = field(default=3)

    maximum_dataframe_size_in_seconds: int = field(default=30)
    entry_buffer_size: int = field(default=20000)

    def __post_init__(self):
        if self.socket_sniffer_binary_path is None:
            self.socket_sniffer_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "socket",
                "socket_sniffer",
            )


@dataclass
class RDMA_SnifferConfig:
    update_interval_by_second: float = field(default=10.0)

    def __post_init__(self):
        pass


@dataclass
class NPUSnifferConfig:
    refresh_interval_by_second: float = field(default=30.0)


@dataclass
class GPUSnifferConfig:
    refresh_interval_by_second: float = field(default=30.0)


@dataclass
class CPUSnifferConfig:
    cache_miss_monitor_binary_path: Optional[str] = field(default=None)
    cpu_sched_monitor_binary_path: Optional[str] = field(default=None)

    msg_style: str = field(default=CacheSnifferConstants.CACHE_SNIFFER_MSG_CSV)
    monitor_report_maximum_interval_by_second: float = field(default=2.0)

    cache_data_file_path: str = field(default="anansi.cache_miss.csv")
    sched_data_file_path: str = field(default="anansi.sched_monitor.csv")
    maximum_log_file_size_in_mb: int = field(default=100)
    maximum_rotation_cnt: int = field(default=3)

    maximum_dataframe_size_in_seconds: int = field(default=30)
    entry_buffer_size: int = field(default=20000)

    def __post_init__(self):
        if self.cache_miss_monitor_binary_path is None:
            self.cache_miss_monitor_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "cache_miss",
                "cache_miss_monitor",
            )
        if self.cpu_sched_monitor_binary_path is None:
            self.cpu_sched_monitor_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "cpu_sched",
                "sched_monitor",
            )


@dataclass
class IPCSnifferEnable:
    uds_enable: bool = field(default=True)
    pipe_enable: bool = field(default=True)
    sysv_msg_enable: bool = field(default=True)
    posix_mq_enable: bool = field(default=True)
    sysv_sem_enable: bool = field(default=True)


@dataclass
class IPCSnifferConfig:
    enable: IPCSnifferEnable = field(default_factory=IPCSnifferEnable)

    uds_sniffer_binary_path: Optional[str] = field(default=None)
    pipe_sniffer_binary_path: Optional[str] = field(default=None)
    sysv_msg_sniffer_binary_path: Optional[str] = field(default=None)
    posix_mq_sniffer_binary_path: Optional[str] = field(default=None)
    sysv_sem_sniffer_binary_path: Optional[str] = field(default=None)

    monitor_report_maximum_interval_by_second: float = field(default=2.0)
    maximum_log_file_size_in_mb: int = field(default=100)
    maximum_rotation_cnt: int = field(default=3)

    def __post_init__(self):
        if isinstance(self.enable, dict):
            self.enable = IPCSnifferEnable(**self.enable)

        if self.uds_sniffer_binary_path is None:
            self.uds_sniffer_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "uds",
                "unix_socket_sniffer",
            )
        if self.pipe_sniffer_binary_path is None:
            self.pipe_sniffer_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "pipe",
                "pipe_sniffer",
            )
        if self.sysv_msg_sniffer_binary_path is None:
            self.sysv_msg_sniffer_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "sysv_msg",
                "sysv_msg_sniffer",
            )
        if self.posix_mq_sniffer_binary_path is None:
            self.posix_mq_sniffer_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "posix_mq",
                "posix_mq_sniffer",
            )
        if self.sysv_sem_sniffer_binary_path is None:
            self.sysv_sem_sniffer_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "sysv_sem",
                "sysv_sem_sniffer",
            )


@dataclass
class HCCSSnifferConfig:
    pmu_monitor_binary_path: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.pmu_monitor_binary_path is None:
            self.pmu_monitor_binary_path = os.path.join(
                PKG_ANANSI_PATH,
                "binary",
                "pmu_monitor",
                "pmu_monitor",
            )


@dataclass
class SnifferConfig:
    socket_sniffer: SocketSnifferConfig = field(default_factory=SocketSnifferConfig)
    npu_sniffer: NPUSnifferConfig = field(default_factory=NPUSnifferConfig)
    gpu_sniffer: GPUSnifferConfig = field(default_factory=GPUSnifferConfig)
    cpu_sniffer: CPUSnifferConfig = field(default_factory=CPUSnifferConfig)
    rdma_sniffer: RDMA_SnifferConfig = field(default_factory=RDMA_SnifferConfig)
    ipc_sniffer: IPCSnifferConfig = field(default_factory=IPCSnifferConfig)
    hccs_sniffer: HCCSSnifferConfig = field(default_factory=HCCSSnifferConfig)

    def __post_init__(self):
        if isinstance(self.socket_sniffer, dict):
            self.socket_sniffer = SocketSnifferConfig(**self.socket_sniffer)
        if isinstance(self.npu_sniffer, dict):
            self.npu_sniffer = NPUSnifferConfig(**self.npu_sniffer)
        if isinstance(self.gpu_sniffer, dict):
            self.gpu_sniffer = GPUSnifferConfig(**self.gpu_sniffer)
        if isinstance(self.cpu_sniffer, dict):
            self.cpu_sniffer = CPUSnifferConfig(**self.cpu_sniffer)
        if isinstance(self.rdma_sniffer, dict):
            self.rdma_sniffer = RDMA_SnifferConfig(**self.rdma_sniffer)
        if isinstance(self.ipc_sniffer, dict):
            self.ipc_sniffer = IPCSnifferConfig(**self.ipc_sniffer)
        if isinstance(self.hccs_sniffer, dict):
            self.hccs_sniffer = HCCSSnifferConfig(**self.hccs_sniffer)
        pass
