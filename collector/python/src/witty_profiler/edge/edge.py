"""Edge definitions and factory for graph connections between entities.

Defines base Edge class and concrete edge types (DirectedEdge, UndirectedEdge)
that represent connections between entities in the topology graph. Integrates
with GlobalIDManager for deduplication and EntityFactory for node management.

Key Components:
    - Edge: Base class for undirected edges with optional weights
    - DirectedEdge: Explicitly tracks source→target direction
    - UndirectedEdge: Symmetric edge connecting two entities
    - EdgeMeta: Metaclass auto-registering edge subclasses
    - EdgeFactory: Singleton factory for edge creation with deduplication

Edge Features:
    - Automatic node entity factory creation/deduplication
    - Weight accumulation via merge_other() for same-edge conflicts
    - Global ID format: `[{edge_type}]{source_global_id}→{target_global_id}`
    - Dataclass integration for serialization (asdict/model_dump)

Directed vs Undirected:
    - DirectedEdge: Tracks explicit source/target; used for IPC, sockets
    - UndirectedEdge: Symmetric relationship (typically for shared memory)
    - Edge: Generic base; nodes list contains both endpoints

Usage:
    ```python
    # Directed edge
    edge = DirectedEdge(
        source_node=ProcessEntity(pid=100),
        target_node=ProcessEntity(pid=200),
        weight=10.5
    )

    # Create via factory
    factory = EdgeFactory.get_instance()
    edge = factory.create_edge({
        "edge_type": "DirectedEdge",
        "source_node": {...},
        "target_node": {...},
        "weight": 5.0
    })

    # Merge edges (for duplicate detection)
    edge1.merge_other(edge2)  # Accumulates weights
    ```

Notes:
    Edge nodes are always deduplicated via EntityFactory. Global ID format
    ensures edges with identical endpoints have identical IDs for deduplication.
    merge_other() is called during graph consolidation when duplicate edges exist.
"""

from abc import ABCMeta
from dataclasses import asdict, dataclass, field

from witty_profiler.common.id_manager import GlobalIDManager, IdObject
from witty_profiler.common.singleton import Singleton
from witty_profiler.entity.entity_base import Entity, EntityFactory


class EdgeMeta(ABCMeta):
    """Metaclass that registers edge subclasses for later lookup."""

    _edge_types = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if not hasattr(cls, "__abstractmethods__") or not cls.__abstractmethods__:
            mcs._edge_types[name] = cls
        cls = dataclass(cls)
        return cls

    @classmethod
    def get_edge_class(mcs, name, default=None):
        return mcs._edge_types.get(name, default)


class Edge(IdObject, metaclass=EdgeMeta):
    """Base class for all edges that tracks member nodes and identifiers."""

    edge_type: str = field(default_factory=lambda: "Edge")
    weight: float | None = field(default=None)

    def __post_init__(self):
        self.edge_type = self.__class__.__name__

    def model_dump(self) -> dict:
        return asdict(self)

    def merge_other(self, other: "Edge") -> "Edge":
        """Merge another edge into this one by combining weights."""
        if not isinstance(other, type(self)):
            raise ValueError("Can only merge with another same instance")
        if self.global_id != other.global_id:
            raise ValueError("Can only merge edges with the same global ID")
        if self.weight is None:
            self.weight = 0.0
        if other.weight is not None:
            self.weight += other.weight
        return self

    @property
    def show_in_compressed_graph(self) -> bool:
        """Whether this edge should be visualized in the compressed graph."""
        return True


class DirectedEdge(Edge):
    """Directed edge that explicitly tracks a source and target node."""

    source_node: Entity | None = None
    target_node: Entity | None = None

    def __post_init__(self):
        super().__post_init__()
        factory: EntityFactory = EntityFactory.get_instance()
        self.source_node = (
            factory.create_entity(self.source_node)
            if not isinstance(self.source_node, Entity)
            else self.source_node
        )
        self.target_node = (
            factory.create_entity(self.target_node)
            if not isinstance(self.target_node, Entity)
            else self.target_node
        )
        self.nodes = self._nodes
        super().__post_init__()

    @property
    def _nodes(self) -> list[Entity]:
        return [self.source_node, self.target_node]

    @property
    def global_id(self) -> str:

        return "relation: {} {} {}".format(
            self.source_node.global_id,
            self.edge_type.removesuffix("Edge"),
            self.target_node.global_id,
        )


class UndirectedEdge(Edge):
    """Undirected edge that links two entities without orientation."""

    nodes: list[Entity] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        factory: EntityFactory = EntityFactory.get_instance()
        # 确保指向同一对象
        self.nodes = sorted([factory.create_entity(node) for node in self.nodes])

    @property
    def global_id(self) -> str:
        return f"[{self.edge_type}]{str([node.global_id for node in self.nodes])}"


class EdgeFactory(Singleton):
    """Singleton factory responsible for instantiating edge instances."""

    def create_edge(self, data: dict | Edge, ensure_unique: bool = False) -> Edge:
        """Create or reuse an edge described by ``data``, optionally ensuring uniqueness."""
        edge = self.hard_create_edge(data)
        if not ensure_unique:
            return edge
        manager = GlobalIDManager.get_instance()
        edge, _ = manager.record_or_get(edge.global_id, edge)
        return edge

    def hard_create_edge(self, data: dict | Edge) -> Edge:
        """Instantiate an edge without consulting the global ID registry."""
        if isinstance(data, Edge):
            return data
        edge_type = data.get("edge_type", "Edge")
        edge_cls = EdgeMeta.get_edge_class(edge_type)
        if edge_cls is None:
            raise ValueError(f"Unknown edge type: {edge_type}")
        return edge_cls(**data)


__all__ = ["Edge", "DirectedEdge", "UndirectedEdge", "EdgeFactory"]
