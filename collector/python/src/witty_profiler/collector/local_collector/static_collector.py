"""
A collector that assign specific static node for graph
"""

from witty_profiler.collector.local_collector.local_collector import StaticLocalCollector
from witty_profiler.common.id_manager import GlobalIDManager
from witty_profiler.common.logging import get_logger
from witty_profiler.entity.node_entity import ProcessEntity
from witty_profiler.graph.graph import Graph

LOGGER = get_logger(__name__)


class StaticCollector(StaticLocalCollector):
    """Singleton Collector"""

    _instance: "StaticCollector" = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(StaticCollector, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.seed_process_pids: list[int] = []
        super().__init__()
        self._initialized = True

    def _get_seed_graph(self):
        seed_nodes = []
        for pid in self.seed_process_pids:
            process: ProcessEntity = ProcessEntity.create_ensure_unique_id(pid=pid)
            if process.alive:
                seed_nodes.append(process)
            else:
                LOGGER.warning(
                    f"Process with pid {pid} is not alive. Skipping it as seed node."
                )
                GlobalIDManager().try_release_global_id(process.global_id)
        return Graph(nodes=seed_nodes, edges=[])

    def add_process_as_seed(self, pid: int):
        self.seed_process_pids.append(pid)

    def supported_source_node_type(self):
        return {}

    def get_neighbors_with_edges(self, entity):
        return [], []
