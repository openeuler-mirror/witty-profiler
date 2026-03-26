import os

from witty_profiler.collector.local_collector.local_collector import LocalCollector
from witty_profiler.common.logging import get_logger
from witty_profiler.common.str_converter import list_to_range_str, range_str_to_list
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.edge.cpu.numa_sniffer import NumaSniffer
from witty_profiler.edge.cpu.numa_edge import (
    AccessWithProcStatusEdge,
    AffinitativeToNuma,
    CacheMissStats,
    NumaAccessEdge,
    NumaAccessInfo,
    NumaSetContainEdge,
    ProcStatus,
    StaticNumaDeployment,
)
from witty_profiler.edge.cpu.sched_sniffer import SchedSniffer
from witty_profiler.edge.cpu.cache_sniffer import CacheSniffer
from witty_profiler.edge.edge import Edge
from witty_profiler.edge.structual.belong import AccessEdge
from witty_profiler.entity.deployment.npu_deployment import NPUDeploymentManager
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity import (
    NumaEntity,
    NumaSetEntity,
    ProcessEntity,
    ThreadEntity,
)
from witty_profiler.entity.node_entity.node_entity import NPUEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class NumaCollector(LocalCollector):
    """
    Collect NUMA topology graph from NUMA, sched, and cachemiss sniffers.
    """

    def start(self):
        self.numa_sniffer.start()
        self.sched_sniffer.start()
        if self.config.enable_cache_miss:
            self.cache_sniffer.start()

    def stop(self):
        self.numa_sniffer.stop()
        self.sched_sniffer.stop()
        if self.config.enable_cache_miss:
            self.cache_sniffer.stop()

    def clear(self):
        # static collect: not needed
        pass

    def __init__(self):
        self.numa_sniffer: NumaSniffer = NumaSniffer()
        self.sched_sniffer: SchedSniffer = SchedSniffer()
        self.cache_sniffer: CacheSniffer = CacheSniffer()
        self.deployment = StaticNumaDeployment()
        mngr = GlobalConfigManager()
        self.config = mngr.get_config().collector_config.numa_collector_config

    def _get_seed_graph(self) -> Graph:
        # 空图
        seed_nodes = list(self.deployment.numa_nodes.values())
        return Graph(nodes=seed_nodes, edges=[])

    def supported_source_node_type(self) -> set[type]:
        return {ProcessEntity, NumaSetEntity, NPUEntity}

    def get_neighbors_with_edges(self, entity) -> tuple[list[Entity], list[Edge]]:
        if isinstance(entity, ProcessEntity):
            return self._get_process_neighbors_with_edges(entity)
        elif isinstance(entity, NumaSetEntity):
            return self._get_numaset_neighbors_with_edges(entity)
        elif isinstance(entity, NPUEntity):
            return self._get_npu_neighbors_with_edges(entity)
            pass
        else:
            return [], []

    def _get_process_neighbors_with_edges(
        self, entity: ProcessEntity
    ) -> tuple[list[Entity], list[Edge]]:

        numa_access_info: NumaAccessInfo = None

        if isinstance(entity, ProcessEntity):
            numa_access_info = self.numa_sniffer.get_numa_access_info_by_pid(entity.pid)
        else:
            return [], []

        if not numa_access_info:
            return [], []

        # Create neighbors and edges with affinity information
        neighbors: list[Entity] = []
        edges: list[Edge] = []
        # Numa set → Numa entity
        # Numa entity → Process/Thread entity
        numa_set = NumaSetEntity.create_ensure_unique_id(
            numa_id_str=numa_access_info.accessed_numa_nodes
        )
        neighbors.append(numa_set)

        cache_miss_stats = None
        if self.config.enable_cache_miss:
            cache_miss_stats = self.cache_sniffer.get_cache_miss_stats_by_pid(entity.pid)

        edges.append(
            NumaAccessEdge.create_ensure_unique_id(
                source_node=entity,
                target_node=numa_set,
                numa_access_info=numa_access_info,
                cache_miss_stats=cache_miss_stats,
            )
        )
        if self.config.enable_thread_node:
            # Also add thread neighbors
            LOGGER.debug(
                "Collecting thread-level NUMA access info for process %s", entity.pid
            )
            thread_neighbors, thread_edges = self._get_thread_neighbors_with_edges(
                entity
            )
            neighbors.extend(thread_neighbors)
            edges.extend(thread_edges)
        return neighbors, edges

    def _get_numaset_neighbors_with_edges(
        self, entity: NumaSetEntity
    ) -> tuple[list[Entity], list[Edge]]:
        numa_list = range_str_to_list(entity.numa_id_str)
        deployment = StaticNumaDeployment()
        numa_list = [
            deployment.numa_nodes.get(numa_id)
            for numa_id in numa_list
            if numa_id in deployment.numa_nodes
        ]
        edges = [
            NumaSetContainEdge.create_ensure_unique_id(
                source_node=entity,
                target_node=numa,
            )
            for numa in numa_list
        ]
        return numa_list, edges

    def _get_thread_neighbors_with_edges(
        self, process: ProcessEntity
    ) -> tuple[list[Entity], list[Edge]]:
        neighbors: list[Entity] = []
        edges: list[Edge] = []

        thread_list = self.numa_sniffer.get_tids_by_pid(process.pid)
        LOGGER.debug(
            "Collecting thread-level NUMA access info for %s threads %s",
            len(thread_list),
            list_to_range_str(thread_list),
        )
        proc_status_info = [
            self.numa_sniffer.get_proc_status_info_by_tid(tid) for tid in thread_list
        ]
        tid2proc_status = {
            tid: info for tid, info in zip(thread_list, proc_status_info) if info
        }
        tid2proc_status = self._filter_proc_status_by_thresh(tid2proc_status)

        for tid, proc_status_info in tid2proc_status.items():
            thread_entity = ThreadEntity.create_ensure_unique_id(
                tid=tid, process=process
            )
            neighbors.append(thread_entity)

            numa_set = NumaSetEntity.create_ensure_unique_id(
                numa_id_str=proc_status_info.accessed_numa_nodes
            )
            neighbors.append(numa_set)

            edges.append(
                AccessWithProcStatusEdge.create_ensure_unique_id(
                    source_node=thread_entity,
                    target_node=numa_set,
                    proc_status=proc_status_info,
                )
            )

        return neighbors, edges

    def _get_npu_neighbors_with_edges(
        self, entity: NPUEntity
    ) -> tuple[list[Entity], list[Edge]]:
        manager = NPUDeploymentManager()
        numa_affinity_list_str: str = manager.query_npu_numa_affinity(entity.id)
        neighbors: list[Entity] = []
        edges: list[Edge] = []
        numa_set = NumaSetEntity.create_ensure_unique_id(
            numa_id_str=numa_affinity_list_str
        )
        neighbors.append(numa_set)
        edges.append(
            AffinitativeToNuma(
                source_node=entity,
                target_node=numa_set,
            )
        )
        return neighbors, edges

    def _filter_proc_status_by_thresh(
        self, tid2proc_status: dict[int, ProcStatus]
    ) -> dict[int, ProcStatus]:
        """
        Filter out threads with low context switch counts
        Args:
            tid2proc_status: Mapping from thread ID to ProcStatus
        Returns:
            Filtered mapping from thread ID to ProcStatus
        """
        # 标准1： 线程上下文切换次数占比阈值
        ctxt_switch_counts = sum(
            info.voluntary_ctxt_switches + info.involuntary_ctxt_switches
            for info in tid2proc_status.values()
        )
        ctxt_switch_thresh = (
            self.config.min_thread_ctxt_switch_pct_thresh * ctxt_switch_counts
        )
        # 标准2: 非自愿上下文切换次数占比阈值
        involuntary_ctxt_switch_counts = sum(
            info.involuntary_ctxt_switches for info in tid2proc_status.values()
        )
        involuntary_ctxt_switch_thresh = (
            self.config.min_thread_ctxt_switch_pct_thresh
            * involuntary_ctxt_switch_counts
        )
        # 标准3: CPU使用阈值
        tid2cpu_time = [
            sum(info.numa_index_to_cpu_runtime.values())
            for info in tid2proc_status.values()
        ]
        cpu_time_thresh = sum(tid2cpu_time) * self.config.min_thread_cpu_pct_thresh

        # 应用: 全部标准取并集
        filtered_tid2proc_status = {
            tid: info
            for tid, info in tid2proc_status.items()
            if (
                info.voluntary_ctxt_switches + info.involuntary_ctxt_switches
                >= ctxt_switch_thresh
            )  # 总context switch次数
            or (
                info.involuntary_ctxt_switches >= involuntary_ctxt_switch_thresh
            )  # 非自愿 context switch次数
            or (sum(info.numa_index_to_cpu_runtime.values()) > cpu_time_thresh)
        }
        return filtered_tid2proc_status
