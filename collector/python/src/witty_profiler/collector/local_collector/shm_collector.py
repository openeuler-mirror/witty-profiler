"""Collects shared memory topology from memory access sniffers.

Builds a topology graph of inter-process memory sharing via POSIX shared
memory (shm), memory-mapped files (mmap), and CUDA pinned memory. Creates
AccessEdge connections to model which processes access shared memory regions.

Edge Types Created:
    - AccessEdge: Process ACCESSES a shared memory region

Seed Graph:
    Starts from all shared memory objects discovered by the sniffer,
    then expands to find all processes accessing each memory region.

Collection Methods:
    - _get_seed_graph(): Extract all shared memory entities from sniffer
    - get_neighbors_with_edges(): For a shared memory region, find all
        processes that access it (create AccessEdge)

Data Sources:
    Uses SharedMemorySniffer (see shmm_sniffer.py) which tracks:
    - POSIX shm (shm_open, shm_unlink)
    - Memory-mapped files (mmap, munmap)
    - CUDA pinned memory regions
    Instrumentation may use eBPF or kernel module based tracing.

Implementation Notes:
    start/stop/clear are currently no-ops as underlying sniffer has no
    persistent resources in this implementation. Memory regions are
    queried on-demand during expansion.

Notes:
    Memory access patterns are collected via access tracking. Each access
    edge accumulates access count and bytes accessed via merge_other().
"""

from queue import Queue
from typing import Tuple

from witty_profiler.collector.local_collector.local_collector import LocalCollector
from witty_profiler.common.logging import get_logger
from witty_profiler.edge.edge import Edge
from witty_profiler.edge.shared_memory.shmm_sniffer import (
    SharedMemorySniffer,
    get_shared_memory_sniffer,
)
from witty_profiler.edge.structual.belong import AccessEdge
from witty_profiler.entity.entity_base import Entity
from witty_profiler.entity.node_entity import ProcessEntity, SharedMemoryEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class SharedMemoryCollector(LocalCollector):
    """Collects shared memory edges."""

    def start(self):
        # No-op start: underlying sniffer has no persistent resources here
        pass

    def stop(self):
        # No-op stop: underlying sniffer has no persistent resources here
        pass

    def clear(self):
        # No-op clear: underlying sniffer has no persistent resources here
        pass

    def __init__(
        self,
        init_visited_entities: list[Entity] = None,
        init_visited_edges: list[Edge] = None,
        max_iterations: int = 10000,
    ):
        self.ignore_entities = (
            {e.global_id for e in init_visited_entities}
            if init_visited_entities
            else set()
        )
        self.ignore_edges = (
            {e.global_id for e in init_visited_edges} if init_visited_edges else set()
        )
        self.sniffer: SharedMemorySniffer = get_shared_memory_sniffer()
        self.max_iterations = max_iterations

    def _get_seed_graph(self) -> Graph:
        shmm_names = self.sniffer.query_all_shm_names()
        shmm_sizes = {
            name: self.sniffer.query_shm_info(name).size
            for name in shmm_names
            if self.sniffer.query_shm_info(name) is not None
        }
        seed_nodes: list[SharedMemoryEntity] = [
            SharedMemoryEntity.create_ensure_unique_id(shm_name=name, shm_size=size)
            for name, size in shmm_sizes.items()
        ]
        return Graph(nodes=seed_nodes, edges=[])

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[list[Entity], list[Edge]]:
        """Return neighbor entities and corresponding access edges.

        For a `ProcessEntity`, neighbors are `SharedMemoryEntity` accessed by the process,
        edges are `AccessEdge(process -> shm)`.
        For a `SharedMemoryEntity`, neighbors are `ProcessEntity` using the shared memory,
        edges are `AccessEdge(process -> shm)`.
        """
        if not isinstance(entity, (ProcessEntity, SharedMemoryEntity)):
            return ([], [])

        neighbors: list[Entity] = []
        edges: list[Edge] = []

        if isinstance(entity, SharedMemoryEntity):
            pids = self.sniffer.query_pid_by_shm_name(entity.shm_name)
            for pid in pids:
                proc = ProcessEntity.create_ensure_unique_id(pid=pid)
                neighbors.append(proc)
                edge = AccessEdge.create_ensure_unique_id(
                    source_node=proc, target_node=entity
                )
                edges.append(edge)
        elif isinstance(entity, ProcessEntity):  # ProcessEntity
            shm_names = self.sniffer.query_shm_by_pid(entity.pid)
            for name in shm_names:
                shm_info = self.sniffer.query_shm_info(name)
                if shm_info is None:
                    # Defensive: skip names without valid info
                    continue
                shm = SharedMemoryEntity.create_ensure_unique_id(
                    shm_name=name, shm_size=shm_info.size
                )
                neighbors.append(shm)
                edge = AccessEdge.create_ensure_unique_id(
                    source_node=entity, target_node=shm
                )
                edges.append(edge)

        return neighbors, edges

    def supported_source_node_type(self) -> set[type]:
        return {ProcessEntity, SharedMemoryEntity}
