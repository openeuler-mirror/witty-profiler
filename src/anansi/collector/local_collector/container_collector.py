from anansi.collector.local_collector.local_collector import LocalCollector
from anansi.edge.docker.docker_sniffer import ContainerSniffer
from anansi.edge.edge import Edge
from anansi.edge.structual.belong import BelongEdge, HostEdge, OwnEdge, RunOnEdge
from anansi.entity.entity_base import Entity
from anansi.entity.node_entity import ContainerEntity, ProcessEntity
from anansi.graph.graph import Graph


class ContainerCollector(LocalCollector):
    """
    Collector for container-related entities and edges.
    """

    def start(self):
        # static collect: not needed
        pass

    def stop(self):
        # static collect: not needed
        pass

    def clear(self):
        # static collect: not needed
        pass

    def __init__(self):
        super().__init__()
        self._sniffer = ContainerSniffer()

    def _get_seed_graph(self) -> Graph:
        # 空图
        return Graph()

    def get_neighbors_with_edges(
        self, process_entity
    ) -> tuple[list[Entity], list[Edge]]:
        """Get the neighbors and edges of a given entity.

        Args:
            entity (Entity): The entity to get the neighbors and edges for.

        Returns:
            tuple[list[Entity], list[Edge]]: A tuple containing the list of neighbors and the list of edges.
        """
        if not isinstance(process_entity, ProcessEntity):
            return [], []

        container = self._sniffer.get_container_by_pid(process_entity.pid)

        if container is None:
            return [], []

        container_entity: ContainerEntity = container
        edges = [
            RunOnEdge.create_ensure_unique_id(
                source_node=process_entity,
                target_node=container_entity,
            ),
            HostEdge.create_ensure_unique_id(
                source_node=container_entity,
                target_node=process_entity,
            ),
        ]
        return [container_entity], edges

    def supported_source_node_type(self) -> set[type]:
        return {ProcessEntity}
