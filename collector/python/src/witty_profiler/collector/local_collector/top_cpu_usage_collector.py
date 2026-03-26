"""
get ProcessEntity for top CPU usage processes
"""

from typing import Tuple

import psutil

from witty_profiler.collector.local_collector.local_collector import StaticLocalCollector
from witty_profiler.edge.edge import Edge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity.node_entity import ProcessEntity
from witty_profiler.graph.graph import Graph


class MainCPUUsageCollector(StaticLocalCollector):

    def __init__(self):
        super().__init__()
        self._pid_set = set()
        self._ignore_pid_set = set()

    def _get_seed_graph(self) -> Graph:
        nodes = [
            ProcessEntity.create_ensure_unique_id(pid=pid)
            for pid in self._get_process_pid_utilizing_cpu_resource_badly()
        ]
        return Graph(nodes=nodes)

    def _get_process_pid_utilizing_cpu_resource_badly(self) -> list[int]:
        """
        Get top CPU usage process PIDs.

        Returns:
            list[int]: List of process IDs sorted by CPU usage in descending order
        """
        processes = []

        for proc in psutil.process_iter(["pid", "cpu_percent"]):
            try:
                pid = proc.info["pid"]
                # Skip ignored PIDs
                if pid in self._ignore_pid_set:
                    continue

                # Get CPU usage percentage
                cpu_percent = proc.info["cpu_percent"]
                if cpu_percent is not None:
                    processes.append((pid, cpu_percent))
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                # Skip processes we can't access
                continue

        # Sort processes by CPU usage in descending order
        processes.sort(key=lambda x: x[1], reverse=True)

        # Return top 10 processes by default
        return [pid for pid, _ in processes[:10]]

    def get_neighbors_with_edges(
        self, entity: ProcessEntity
    ) -> Tuple[list[Entity], list[Edge]]:
        return []

    def supported_source_node_type(self) -> set[type]:
        return {}


__all__ = ["MainCPUUsageCollector"]
