from typing import cast

from anansi.common.logging import get_logger
from anansi.config_manager.config_manager import GlobalConfigManager

from ...edge.edge import Edge
from ...entity.entity_base import Entity
from ...entity.node_entity.node_entity import ProcessEntity
from ...graph.graph import Graph
from .local_collector import StaticLocalCollector


class CommonProcessParentCollector(StaticLocalCollector):
    """
    Collector that collects parent-child relationships between processes based on their PID and PPID.
    if process with PID A has been observed for multiple times as parent process to other processes,
    then we will consider A as a common parent process add the process
    """

    def __init__(self):
        super().__init__()
        self._candidate_ppid2child_pid: dict[int, set[int]] = {}
        self._pid_to_depth: dict[int, int] = {}
        self._config = (
            GlobalConfigManager()
            .get_config()
            .collector_config.common_process_parent_collector_config
        )

    def clear(self):
        self._candidate_ppid2child_pid.clear()
        self._pid_to_depth.clear()

    def _get_seed_graph(self) -> Graph:
        self.clear()
        return Graph()

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> tuple[list[Entity], list[Edge]]:
        if not isinstance(entity, ProcessEntity):
            return [], []

        single_parent_extend_left = self._config.single_node_parent_depth
        tmp_entity = entity
        while (
            single_parent_extend_left > 0
            and tmp_entity.pid in self._candidate_ppid2child_pid  # 当前节点存在子节点
            and len(self._candidate_ppid2child_pid[tmp_entity.pid])
            == 1  # 当前节点只有一个子节点
        ):
            single_parent_extend_left -= 1
            child_pid = list(self._candidate_ppid2child_pid[tmp_entity.pid])[0]
            tmp_entity = ProcessEntity.create_ensure_unique_id(pid=child_pid)
        neighbors = self.lookup_extend_parent(
            entity,
            single_parent_extend_left=single_parent_extend_left,
        )

        return neighbors, []

    def lookup_extend_parent(
        self,
        cur_process: ProcessEntity,
        single_parent_extend_left: int = 1,
    ) -> list[ProcessEntity]:
        """
        Look up the parent process of the current process and add it to the neighbors list if it is a common parent process.
        We will only look up one level of parent process to avoid introducing too much noise, as the parent-child relationship can be very noisy.
        """
        if cur_process.pid not in self._pid_to_depth:
            self._pid_to_depth[cur_process.pid] = single_parent_extend_left
        elif single_parent_extend_left > self._pid_to_depth[cur_process.pid]:
            self._pid_to_depth[cur_process.pid] = single_parent_extend_left
        else:
            # fast bypass if we have already looked up this process with same or more extend left
            return []

        neighbors: list[ProcessEntity] = []
        ppid = cur_process.ppid
        if ppid > 0:
            self._candidate_ppid2child_pid.setdefault(ppid, set()).add(cur_process.pid)
            if (
                len(self._candidate_ppid2child_pid[ppid]) >= 2
            ):  # directly extend to parent if it is already a common parent
                parent_process = ProcessEntity.create_ensure_unique_id(pid=ppid)
                neighbors.append(parent_process)
                neighbors.extend(
                    self.lookup_extend_parent(
                        parent_process,
                        single_parent_extend_left=single_parent_extend_left,
                    )
                )
            elif (
                single_parent_extend_left > 0
            ):  # if not, we can still look up one level of parent process to enable exploration
                parent_process = ProcessEntity.create_ensure_unique_id(pid=ppid)
                neighbors.append(parent_process)
                neighbors.extend(
                    self.lookup_extend_parent(
                        parent_process,
                        single_parent_extend_left=single_parent_extend_left - 1,
                    )
                )
        return neighbors

    def supported_source_node_type(self) -> set[type]:
        return {ProcessEntity}


__all__ = ["CommonProcessParentCollector"]
