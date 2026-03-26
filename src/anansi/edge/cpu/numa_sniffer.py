import glob
import json
import os
import re
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Set

from anansi.common.constants import ProcConstants as PC
from anansi.common.constants import SchedMonitorColumn
from anansi.common.logging import get_logger
from anansi.common.str_converter import list_to_range_str, range_str_to_list
from anansi.entity.entity_base import Entity
from anansi.entity.node_entity import ProcessEntity, ThreadEntity

from .numa_deployment import StaticNumaDeployment
from .numa_edge import (
    NumaAccessEdge,
    NumaAccessInfo,
    NumaAffinityInfo,
    ProcStatus,
    StaticNumaDeployment,
)
from .sched_sniffer import SchedSniffer, get_sched_sniffer

LOGGER = get_logger(__name__)


class NumaSniffer:
    """
    This class provides an interface to query NUMA information
    """

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def __init__(self):
        self.deployment = StaticNumaDeployment()
        self._sched_sniffer: SchedSniffer = get_sched_sniffer()
        self.pid_access_cache: Dict[int, NumaAccessInfo] = {}

    @classmethod
    def get_tids_by_pid(cls, pid: int) -> list[int]:
        """
        Get all thread IDs for a given process ID via /proc/<pid>/task/

        Args:
            pid: Process ID
        """
        try:
            return [int(tid) for tid in os.listdir(f"/proc/{pid}/task")]
        except Exception as e:
            LOGGER.error(f"Failed to get threads for process {pid}: {e}")
            return []

    def get_numa_access_info_by_pid(self, pid: int) -> Optional[NumaAccessInfo]:
        """
        Get NUMA access information for a process

        Args:
            pid: Process ID

        Returns:
            NUMA access information for the process
        """
        root_path = f"/proc/{pid}"
        try:
            with open(f"{root_path}/numa_maps", "r") as f:
                lines = f.readlines()
        except FileNotFoundError as e:
            LOGGER.warning(
                f"{root_path}/numa_maps not found (might be a short-lived process or a pid in namespace), skipping."
            )
            return None
        except PermissionError:
            LOGGER.error(f"Error: Permission denied to read {root_path}/numa_maps.")
            return None

        # 统计每个 NUMA 节点的页数（默认页大小 4KB）
        node_pages = defaultdict(int)
        read_only_pages = defaultdict(int)
        dirty_anon_pages = defaultdict(int)

        # 正则匹配 N<node>=<count>
        numa_pattern = re.compile(r"N(\d+)=(\d+)")

        # 辅助正则：提取 anon, dirty, file 等字段
        anon_pattern = re.compile(r"anon=(\d+)")
        dirty_pattern = re.compile(r"dirty=(\d+)")
        file_pattern = re.compile(r"file=")

        for line in lines:
            # 跳过空行
            line = line.strip()
            if not line:
                continue

            # 提取所有 N<node>=<count> 对
            numa_matches = numa_pattern.findall(line)
            if not numa_matches:
                continue

            # 判断是否为只读映射（来自文件且无 anon）
            has_file = bool(file_pattern.search(line))
            anon_match = anon_pattern.search(line)
            dirty_match = dirty_pattern.search(line)

            anon_val = int(anon_match.group(1)) if anon_match else 0
            dirty_val = int(dirty_match.group(1)) if dirty_match else 0

            # 判断类型
            is_read_only = has_file and anon_val == 0
            is_dirty_anon = anon_val > 0 and dirty_val > 0

            # 累加各节点页数
            for node_str, count_str in numa_matches:
                node = int(node_str)
                count = int(count_str)

                node_pages[node] += count

                if is_read_only:
                    read_only_pages[node] += count
                if is_dirty_anon:
                    dirty_anon_pages[node] += count

        node_pages = dict(sorted(node_pages.items()))
        read_only_pages = dict(sorted(read_only_pages.items()))
        dirty_anon_pages = dict(sorted(dirty_anon_pages.items()))

        # 构造 NumaAccessInfo
        proc_status: ProcStatus = self._read_cpu_status(pid=pid)

        process_numa2cpu_time = self._sched_sniffer.get_numa_cpu_time_by_tgid(pid)
        numa_access_info = NumaAccessInfo(
            total_pages=dict(node_pages),
            read_only_pages=dict(read_only_pages),
            dirty_anon_pages=dict(dirty_anon_pages),
            proc_status=proc_status,
            numa_affinity_info=NumaAffinityInfo(
                cpu_runtime_pct_in_each_numa=[
                    process_numa2cpu_time.get(i, 0.0)
                    for i in StaticNumaDeployment().numa_nodes
                ],
                mem_pages_in_each_numa=[
                    dirty_anon_pages.get(i, 0.0)
                    for i in StaticNumaDeployment().numa_nodes
                ],
            ),
        )
        return numa_access_info

    def get_numa_access_info_by_process(
        self, process: ProcessEntity
    ) -> Optional[NumaAccessInfo]:
        return self.get_numa_access_info_by_pid(process.pid)

    def get_proc_status_info_by_tid(self, tid: int) -> Optional[ProcStatus]:
        # linux light weight thread model
        return self._read_cpu_status(pid=tid)

    def get_numa_access_info_by_thread(
        self, thread: ThreadEntity
    ) -> Optional[ProcStatus]:
        return self.get_proc_status_info_by_tid(thread.tid)

    def _read_cpu_status(self, pid: int) -> ProcStatus:
        proc_status = {}
        root_path = f"/proc/{pid}"
        try:
            with open(f"{root_path}/status", "r") as f:
                lines = f.readlines()
                proc_status = {
                    k.strip(): v.strip()
                    for line in lines
                    for k, v in [line.split(":", 1)]
                }
        except FileNotFoundError:
            proc_status = {}

        accessed = self._sched_sniffer.get_sched_df_by_pid(pid)
        accessed_cpu = accessed[SchedMonitorColumn.CPU].unique().tolist()
        accessed_numa2cpu_time = self._sched_sniffer.get_numa_cpu_time_by_pid(pid)

        return ProcStatus(
            voluntary_ctxt_switches=int(proc_status.get(PC.VOLUNTARY_CTX_SWITCHES, -1)),
            involuntary_ctxt_switches=int(
                proc_status.get(PC.NONVOLUNTARY_CTX_SWITCHES, -1)
            ),
            cpus_allowed_list=proc_status.get(PC.CPUS_ALLOWED_LIST, ""),
            cpus_preferred_list=proc_status.get(PC.CPUS_PREFERRED_LIST, ""),
            cpus_accessed_list=list_to_range_str(accessed_cpu),
            numa_index_to_cpu_runtime=accessed_numa2cpu_time,
            mems_allowed_list=proc_status.get(PC.MEMS_ALLOWED_LIST, ""),
        )


if __name__ == "__main__":

    sniffer = NumaSniffer()
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--numa", action="store_true", help="print numa info")
    parser.add_argument("--pid", type=int, help="Process ID to query NUMA affinity")
    parser.add_argument("--tid", type=int, help="Thread ID to query NUMA affinity")
    args = parser.parse_args()
    if args.numa:
        LOGGER.info("Static NUMA Deployment:\n%s", sniffer.deployment)
    elif args.tid:
        LOGGER.info(
            "Querying NUMA access for PID %s, TID %s:\n%s",
            args.pid,
            args.tid,
            sniffer.get_proc_status_info_by_tid(args.tid),
        )
    elif args.pid:

        LOGGER.info(
            "Querying NUMA access for PID %s:\n%s",
            args.pid,
            sniffer.get_numa_access_info_by_pid(args.pid),
        )
