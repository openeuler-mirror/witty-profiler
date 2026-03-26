from dataclasses import dataclass, field
from typing import Optional

from witty_profiler.entity.entity_base import Entity

from .server_config import RemoteSlaveConfig, ServerAddr


@dataclass
class SocketCollectorConfig:
    enable_thread_node: bool = field(default=True)  # 是否创建线程节点
    min_thread_packet_threshold: int = field(
        default=10
    )  # 线程节点最小发送/接受数据包数
    enable_filter: bool = field(default=True)  # 是否启用连接过滤
    filter_conn_packet_cnt: int = field(default=5)  # 筛选连接数据包数
    filter_conn_data_size: int = field(default=240)


@dataclass
class NumaCollectorConfig:
    enable_thread_node: bool = field(default=True)  # 是否创建线程节点
    min_thread_ctxt_switch_pct_thresh: float = field(default=0.1)
    min_thread_cpu_pct_thresh: float = field(default=0.1)
    enable_cache_miss: bool = field(default=True)  # 是否启用 cache miss 采集


@dataclass
class RDMACollectorConfig:
    enable_thread_node: bool = field(default=True)  # 是否创建线程节点
    min_thread_rdma_ops_thresh: int = field(default=10)


@dataclass
class CommonProcessParentCollectorConfig:
    """
    Collector config for CommonProcessParentCollector
    """

    single_node_parent_depth: int = field(default=1)


@dataclass
class HCCSCollectorConfig:
    """Collector config for HCCSCollector.

    Attributes:
        cpu_type: Huawei CPU type ("auto_detect" or specific CPU type like "920B", "920C", "920E", "920F")
        interval_ms: Sampling interval in milliseconds
        enable_ddr_bandwidth: Enable DDR bandwidth collection
        enable_hha_bandwidth: Enable HHA bandwidth collection
        enable_l3c_bandwidth: Enable L3C bandwidth collection
        enable_pa_bandwidth: Enable PA bandwidth collection
        target_sccls: Target SCCL IDs to monitor (comma-separated string, e.g., "1,3,5"). Empty means all.
    """

    cpu_type: str = field(
        default="auto_detect"
    )  # "auto_detect" or specific CPU type like "920B", "920C", etc.
    interval_ms: int = field(default=200)
    enable_ddr_bandwidth: bool = field(default=True)
    enable_hha_bandwidth: bool = field(default=True)
    enable_l3c_bandwidth: bool = field(default=True)
    enable_pa_bandwidth: bool = field(default=True)
    target_sccls: str = field(default="")  # Empty means all SCCLs


@dataclass
class CollectorConfig:
    start_nodes: list[Entity] = field(default_factory=list)
    disabled_collectors: list[str] = field(default_factory=list)
    remote_slaves: Optional[list["RemoteSlaveConfig"]] = field(
        default_factory=lambda: [
            RemoteSlaveConfig(slave_addr=ServerAddr(host="127.0.0.1", port=-1))
        ]  # default invalid slave as template
    )
    seed_graph_collectors: list[str] = field(
        default_factory=lambda: [
            "NPUCollector",
            "GPUCollector",
            "RemoteCollector",
            "NumaCollector",
            "RDMACollector",
            "StaticCollector",
            "CommonProcessParentCollector",
        ]
    )

    socket_collector_config: SocketCollectorConfig = field(
        default_factory=SocketCollectorConfig
    )

    numa_collector_config: NumaCollectorConfig = field(
        default_factory=NumaCollectorConfig
    )

    rdma_collector_config: RDMACollectorConfig = field(
        default_factory=RDMACollectorConfig
    )

    common_process_parent_collector_config: CommonProcessParentCollectorConfig = field(
        default_factory=CommonProcessParentCollectorConfig
    )

    hccs_collector_config: HCCSCollectorConfig = field(
        default_factory=HCCSCollectorConfig
    )

    def __post_init__(self):
        # lazy import to avoid circular import
        # pylint: disable=import-outside-toplevel
        from witty_profiler.entity.entity_base import EntityFactory

        ent_factory: EntityFactory = EntityFactory.get_instance()
        self.start_nodes = [
            ent_factory.create_entity(node) for node in self.start_nodes
        ]
        self.remote_slaves = [
            RemoteSlaveConfig(**slave) if isinstance(slave, dict) else slave
            for slave in self.remote_slaves
            if isinstance(slave, (dict, RemoteSlaveConfig))
        ]
        self.socket_collector_config = (
            SocketCollectorConfig(**self.socket_collector_config)
            if isinstance(self.socket_collector_config, dict)
            else self.socket_collector_config
        )

        self.numa_collector_config = (
            NumaCollectorConfig(**self.numa_collector_config)
            if isinstance(self.numa_collector_config, dict)
            else self.numa_collector_config
        )

        self.rdma_collector_config = (
            RDMACollectorConfig(**self.rdma_collector_config)
            if isinstance(self.rdma_collector_config, dict)
            else self.rdma_collector_config
        )

        self.common_process_parent_collector_config = (
            CommonProcessParentCollectorConfig(
                **self.common_process_parent_collector_config
            )
            if isinstance(self.common_process_parent_collector_config, dict)
            else self.common_process_parent_collector_config
        )

        self.hccs_collector_config = (
            HCCSCollectorConfig(**self.hccs_collector_config)
            if isinstance(self.hccs_collector_config, dict)
            else self.hccs_collector_config
        )
