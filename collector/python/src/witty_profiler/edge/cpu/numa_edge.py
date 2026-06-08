import glob
import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Set

from witty_profiler.common.logging import get_logger
from witty_profiler.common.str_converter import list_to_range_str, range_str_to_list
from witty_profiler.edge.cpu.numa_deployment import StaticNumaDeployment
from witty_profiler.edge.edge import DirectedEdge
from witty_profiler.edge.edge_category import DataStreamEdge, DeployEdge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity import NumaEntity, ProcessEntity
from witty_profiler.entity.node_entity.node_entity import NumaSetEntity

LOGGER = get_logger(__name__)


@dataclass
class NumaAffinityInfo:
    """NUMA affinity information for a process/thread.

    Attributes:
        cpu_affinity_weight: Affinity score vector
        mem_affinity_weight: Affinity score vector
        affinity_match_score: Overall affinity match score
    """

    cpu_runtime_pct_in_each_numa: list = field(default_factory=lambda: [1])
    mem_pages_in_each_numa: list = field(default_factory=lambda: [1])
    total_dirty_anon_pages: int = field(default_factory=lambda: None)
    cpu_mem_access_cosine_similarity: float = field(default_factory=lambda: None)

    def __post_init__(self):
        total_time = sum(self.cpu_runtime_pct_in_each_numa) + 1e-10
        self.cpu_runtime_pct_in_each_numa = [
            float(e / total_time) for e in self.cpu_runtime_pct_in_each_numa
        ]
        self.total_dirty_anon_pages = int(sum(self.mem_pages_in_each_numa))
        self.mem_pages_in_each_numa = list(map(int, self.mem_pages_in_each_numa))
        if self.cpu_mem_access_cosine_similarity is None:
            if self.total_dirty_anon_pages == 0:
                self.cpu_mem_access_cosine_similarity = 0.0
            else:
                self.cpu_mem_access_cosine_similarity = sum(
                    [
                        pct * page / self.total_dirty_anon_pages
                        for pct, page in zip(
                            self.cpu_runtime_pct_in_each_numa, self.mem_pages_in_each_numa
                        )
                    ]
                )

    def __str__(self) -> str:
        # return f"[NumaAffinity]{json.dumps(asdict(self), indent=2)}"
        return f"[NumaAffinity]{self.__dict__}"

    @property
    def accessed_numa_nodes(self) -> str:
        accessed = set()
        for i, pct in enumerate(self.cpu_runtime_pct_in_each_numa):
            if pct > 0:
                accessed.add(i)
        for i, page in enumerate(self.mem_pages_in_each_numa):
            if page > 0:
                accessed.add(i)
        return list_to_range_str(list(accessed))


@dataclass
class ProcStatus:
    voluntary_ctxt_switches: int = field(default_factory=lambda: -1)
    involuntary_ctxt_switches: int = field(default_factory=lambda: -1)
    cpus_allowed_list: str = field(default_factory=lambda: "")
    cpus_preferred_list: str = field(default_factory=lambda: "")
    cpus_accessed_list: str = field(default_factory=lambda: "")
    mems_allowed_list: str = field(default_factory=lambda: "")
    numa_index_to_cpu_runtime: dict[int, float] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.cpus_allowed_list, list):
            self.cpus_allowed_list = list_to_range_str(self.cpus_allowed_list)
        if isinstance(self.cpus_preferred_list, list):
            self.cpus_preferred_list = list_to_range_str(self.cpus_preferred_list)
        if isinstance(self.mems_allowed_list, list):
            self.mems_allowed_list = list_to_range_str(self.mems_allowed_list)

    @property
    def accessed_numa_nodes(self) -> str:
        return list_to_range_str(
            StaticNumaDeployment().query_numa_id_by_cpu(self.cpus_allowed_list)
        )

    def get_accessed_numa_set_node(self, unique: bool = True) -> NumaSetEntity:
        if unique:
            return NumaSetEntity.create_ensure_unique_id(
                numa_id_str=self.accessed_numa_nodes
            )
        else:
            return NumaSetEntity(numa_id_str=self.accessed_numa_nodes)

    def __str__(self) -> str:
        dict_data = asdict(self)
        dict_data.pop("mems_allowed_list", None)
        dict_data.pop("cpus_preferred_list", None)
        return f"[ProcStatus]{dict_data}"


@dataclass
class CacheMissStats:
    """Cache miss statistics grouped by NUMA node."""

    all_numa_ids: list[int] = field(default_factory=list)
    numa_id_to_l1i_miss: dict[int, int] = field(default_factory=dict)
    numa_id_to_llc_miss: dict[int, int] = field(default_factory=dict)
    numa_id_to_total_miss: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.numa_id_to_l1i_miss = self._normalize_mapping(self.numa_id_to_l1i_miss)
        self.numa_id_to_llc_miss = self._normalize_mapping(self.numa_id_to_llc_miss)
        self.numa_id_to_total_miss = self._normalize_mapping(self.numa_id_to_total_miss)

    @staticmethod
    def _normalize_mapping(
        mapping: dict[int, int] | dict[str, int] | None,
    ) -> dict[int, int]:
        if not mapping:
            return {}
        return {int(numa_id): int(value) for numa_id, value in mapping.items()}

    @property
    def total_miss(self) -> int:
        """Get total cache miss count across all NUMA nodes."""
        return sum(self.numa_id_to_total_miss.values())

    @property
    def accessed_numa_nodes(self) -> str:
        """Return the NUMA nodes that have cache miss records."""
        numa_ids = {
            numa_id
            for mapping in (
                self.numa_id_to_l1i_miss,
                self.numa_id_to_llc_miss,
                self.numa_id_to_total_miss,
            )
            for numa_id, value in mapping.items()
            if value > 0
        }
        return list_to_range_str(sorted(numa_ids))

    @property
    def ordered_numa_ids(self) -> list[int]:
        """Return sorted NUMA ids represented by this cache miss payload."""
        if self.all_numa_ids:
            return self.all_numa_ids
        return sorted(
            set(self.numa_id_to_l1i_miss)
            | set(self.numa_id_to_llc_miss)
            | set(self.numa_id_to_total_miss)
        )

    @staticmethod
    def _mapping_to_list(mapping: dict[int, int], ordered_numa_ids: list[int]) -> list[int]:
        return [int(mapping.get(numa_id, 0)) for numa_id in ordered_numa_ids]

    @property
    def formatted_stats(self) -> dict[str, list[int]]:
        """Return cache miss counters as ordered lists aligned to the NUMA set."""
        ordered_numa_ids = self.ordered_numa_ids
        return {
            "l1i_miss": self._mapping_to_list(
                self.numa_id_to_l1i_miss,
                ordered_numa_ids,
            ),
            "llc_miss": self._mapping_to_list(
                self.numa_id_to_llc_miss,
                ordered_numa_ids,
            ),
            "total_miss": self._mapping_to_list(
                self.numa_id_to_total_miss,
                ordered_numa_ids,
            ),
        }

    def __str__(self) -> str:
        return f"[CacheMissStats]{self.formatted_stats}"


@dataclass
class NumaAccessInfo:
    """
    This class represents the access pattern of a Process/Thead to NUMA node
    """

    proc_status: ProcStatus = field(default_factory=lambda: ProcStatus())
    read_only_pages: dict[int, int] = field(default_factory=dict)
    dirty_anon_pages: dict[int, int] = field(default_factory=dict)
    total_pages: dict[int, int] = field(default_factory=dict)
    numa_affinity_info: NumaAffinityInfo = field(default_factory=lambda: None)

    def __post_init__(self) -> None:
        if isinstance(self.proc_status, dict):
            self.proc_status = ProcStatus(**self.proc_status)
        if isinstance(self.numa_affinity_info, dict):
            self.numa_affinity_info = NumaAffinityInfo(**self.numa_affinity_info)

    @property
    def accessed_numa_nodes(self) -> str:
        return self.numa_affinity_info.accessed_numa_nodes

    def unique_id(self) -> str:
        return str(sorted(self.accessed_numa_nodes))

    def __str__(self) -> str:
        return f"[NumaAccessInfo]\n" f"{json.dumps(asdict(self), indent=2)}"


class NumaAccessEdge(DataStreamEdge):
    """NUMA access edge representing the relationship between a process/thread and a NUMA node.

    Attributes:
        source_node: The process or thread entity
        target_node: The NUMA node entity
        affinity_weight: Affinity score (0.0-1.0), higher means stronger binding
            - 1.0: Only this NUMA node is allowed (exclusive affinity)
            - 0.0-1.0: Proportional to the number of allowed CPUs on this node
        cpu_set: List of CPU IDs on this NUMA node that the process can use (sorted)
        has_memory_usage: Whether the process has memory allocated on this NUMA node
        numa_access_info: NUMA access information including affinity data.
        cache_miss_stats: Optional cache miss statistics for this relationship.
    """

    source_node: ProcessEntity = field(default_factory=ProcessEntity)
    target_node: NumaSetEntity = field(default_factory=NumaSetEntity)

    # Affinity-related attributes
    numa_access_info: NumaAccessInfo = field(default_factory=lambda: None)
    cache_miss_stats: CacheMissStats | None = field(default_factory=lambda: None)

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.numa_access_info, dict):
            self.numa_access_info = NumaAccessInfo(**self.numa_access_info)
        if not isinstance(self.numa_access_info, NumaAccessInfo):
            raise ValueError(f"Invalid NumaAccessInfo: {self.numa_access_info}")

        if isinstance(self.cache_miss_stats, dict):
            self.cache_miss_stats = CacheMissStats(**self.cache_miss_stats)
        if self.cache_miss_stats is not None and not isinstance(self.cache_miss_stats, CacheMissStats):
            raise ValueError(f"Invalid CacheMissStats: {self.cache_miss_stats}")

    def __str__(self) -> str:
        parts = []
        if self.numa_access_info and self.numa_access_info.numa_affinity_info:
            parts.append(str(self.numa_access_info.numa_affinity_info))
        if self.cache_miss_stats:
            parts.append(str(self.cache_miss_stats))
        if parts:
            return f"{super().__str__()}({', '.join(parts)})"
        return super().__str__()


class AccessWithProcStatusEdge(DataStreamEdge):
    """Process status edge representing the status information of a process/thread.

    Attributes:
        source_node: The process or thread entity
        target_node: NumaSet entity
        proc_status: The process/thread status information
    """

    source_node: ProcessEntity = field(default_factory=ProcessEntity)
    target_node: NumaSetEntity = field(default_factory=NumaSetEntity)
    proc_status: ProcStatus = field(default_factory=lambda: ProcStatus())

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.proc_status, dict):
            self.proc_status = ProcStatus(**self.proc_status)

    def __str__(self) -> str:
        return f"{super().__str__()} with stats:({self.proc_status})"


class AffinitativeToNuma(DataStreamEdge):
    """Affinity edge representing the overall affinity relationship between a entity
    and a NUMA node set.

    Attributes:
        source_node: The entity
        target_node: The NUMA node set entity
        affinity_info: The overall affinity information to the NUMA node set
    """

    source_node: Entity = field(default_factory=Entity)
    target_node: NumaSetEntity = field(default_factory=NumaSetEntity)

    def __post_init__(self):
        super().__post_init__()


class NumaSetContainEdge(DataStreamEdge):
    """Containment edge representing the relationship between a NUMA node set and individual NUMA nodes.

    Attributes:
        source_node: The NUMA node set entity
        target_node: The individual NUMA node entity
    """

    source_node: NumaSetEntity = field(default_factory=NumaSetEntity)
    target_node: NumaEntity = field(default_factory=NumaEntity)

    def __post_init__(self):
        super().__post_init__()

    @property
    def show_in_compressed_graph(self):
        return False


__all__ = [
    "NumaAccessEdge",
    "AccessWithProcStatusEdge",
    "AffinitativeToNuma",
    "NumaSetContainEdge",
]
