"""Defines the immutable graph structure for system topology representation.

Provides the core Graph class that maintains nodes (Entity objects) and edges
(Edge objects) to represent inter-process communication and control dependencies
in AI training/inferencing systems. The graph is immutable after creation but
supports lazy expansion via `try_add_node()` and `try_add_edge()` methods.

Key Components:
    - Graph: Immutable dataclass containing Entity nodes and Edge connections,
        using factory pattern for entity/edge instantiation and deduplication
    - GraphMeta: Metaclass ensuring Graph is properly wrapped as a dataclass

Features:
    - Automatic entity/edge factory instantiation via __post_init__
    - Duplicate node and edge elimination via global ID tracking
    - Node and edge membership queries (contains_node, contains_edge)
    - Graph merging and comparison operators (>=, <=, ==, +)
    - JSON serialization via model_dump()

Notes:
    The nodes list is immutable after Graph creation; modifications are only
    allowed via try_add_node()/try_add_edge() methods. Edges automatically add
    their endpoint nodes to the graph if missing.
"""

import json
from abc import ABC, ABCMeta
from dataclasses import asdict, dataclass, field
from typing import Any

from anansi.common.env_manager import EnvInfo
from anansi.common.logging import get_logger
from anansi.edge.edge import DirectedEdge, Edge, EdgeFactory
from anansi.entity.entity_base import Entity, EntityFactory
from anansi.entity.entity_namespace import EntityNameSpace

LOGGER = get_logger(__name__)


class GraphMeta(ABCMeta):
    """Meta class to ensure Graph is a dataclass"""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if not hasattr(cls, "__dataclass_fields__"):
            cls = dataclass(cls)
        return cls


class Graph(ABC, metaclass=GraphMeta):
    """
    Graph structure containing nodes and edges
    the nodes should not be edited once the graph is created
    """

    nodes: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def __post_init__(self):
        ent_fact: EntityFactory = EntityFactory.get_instance()

        # 先转为Entity/Edge对象
        self.nodes = [
            ent_fact.create_entity(node) if not isinstance(node, Entity) else node
            for node in self.nodes
        ]
        edg_fact: EdgeFactory = EdgeFactory.get_instance()
        self.edges = [
            edg_fact.create_edge(edge) if not isinstance(edge, Edge) else edge
            for edge in self.edges
        ]
        # 去重准备
        id2nodes = {node.global_id: node for node in self.nodes}

        # 如果有没存在的Entity: 添加进去
        for edge in self.edges:
            for _, node in enumerate(edge.nodes):
                if node.global_id not in id2nodes:
                    # 补充边里的节点
                    id2nodes[node.global_id] = node
                    self.nodes.append(node)
        self._id2nodes = id2nodes
        self._id2edges = {edge.global_id: edge for edge in self.edges}

        # 去重
        self.nodes = list(self._id2nodes.values())
        self.edges = list(self._id2edges.values())

    def contains_node(self, node: Entity) -> bool:
        """检查节点是否存在于图中"""
        return node.global_id in self._id2nodes

    def contains_edge(self, edge: Edge) -> bool:
        """检查边是否存在于图中"""
        return edge.global_id in self._id2edges

    def try_add_node(self, node: Entity):
        """尝试添加节点"""
        if node.global_id not in self._id2nodes:
            self.nodes.append(node)
            self._id2nodes[node.global_id] = node

    def try_add_edge(self, edge: Edge, merge_enable=False):
        """添加边（与对应节点）到拓扑图中"""
        if edge.global_id not in self._id2edges:
            self.edges.append(edge)
            self._id2edges[edge.global_id] = edge
        elif merge_enable:
            # 合并边
            existing_edge = self._id2edges[edge.global_id]
            existing_edge.merge_other(edge)

        for node in edge.nodes:
            self.try_add_node(node)

    def model_dump(self) -> dict:
        """转为json"""
        return asdict(self)

    def model_dump_json(self, *args, **kwargs) -> str:
        """转为json"""
        return json.dumps(self.model_dump(), *args, **kwargs)

    def describe(self) -> str:
        """图描述信息"""
        msg = ""
        msg += f"Graph with {len(self.nodes)} nodes and {len(self.edges)} edges\n"
        msg += "Nodes:\n"
        for node in self.nodes:
            msg += f"  - {node}\n"
        msg += "Edges:\n"
        for edge in self.edges:
            if not edge.show_in_compressed_graph:
                continue
            msg += f"  - {edge}\n"
        return msg

    def to_mermaid_text(self) -> str:
        """转为mermaid文本"""
        lines: list[str] = ["graph TD"]
        node_id_map: dict[str, str] = {}

        def escape_label(label: str) -> str:
            return label.replace("\\n", " ").replace('"', '\\"')

        def ensure_node(node: Entity) -> str:
            node_key = node.global_id
            if node_key not in node_id_map:
                node_id_map[node_key] = f"N{len(node_id_map)}"
                label = escape_label(node.global_id)
                lines.append(f'    {node_id_map[node_key]}["{label}"]')
            return node_id_map[node_key]

        for node in sorted(self.nodes, key=lambda n: n.global_id):
            ensure_node(node)

        for edge in sorted(self.edges, key=lambda e: e.global_id):
            if not edge.show_in_compressed_graph:
                continue

            if isinstance(edge, DirectedEdge) and edge.source_node and edge.target_node:
                source_node = edge.source_node
                target_node = edge.target_node
                arrow = "-->"
            else:
                nodes = getattr(edge, "nodes", [])
                if len(nodes) < 2:
                    continue
                source_node = nodes[0]
                target_node = nodes[1]
                arrow = "--"

            source_id = ensure_node(source_node)
            target_id = ensure_node(target_node)

            label = edge.edge_type.removesuffix("Edge")
            if label and label != "Edge":
                lines.append(f"    {source_id} {arrow}|{label}| {target_id}")
            else:
                lines.append(f"    {source_id} {arrow} {target_id}")

        return "\n".join(lines)

    def __str__(self) -> str:
        return self.describe()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Graph):
            return False

        return self <= other <= self

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Graph):
            raise RuntimeError("Can only compare with another Graph")

        if any(e.global_id not in self._id2nodes for e in other.nodes):
            return False

        if any(e.global_id not in self._id2edges for e in other.edges):
            return False

        return True

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Graph):
            raise RuntimeError("Can only compare with another Graph")

        if any(e not in other.nodes for e in self.nodes):
            return False

        if any(e.global_id not in other._id2edges for e in self.edges):
            return False

        return True

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, Entity):
            return self.contains_node(item)
        elif isinstance(item, Edge):
            return self.contains_edge(item)
        else:
            raise TypeError(f"{item} is not a valid entity or edge")

    def __add__(self, other: "Graph") -> "Graph":
        return Graph(self.nodes + other.nodes, self.edges + other.edges)

    @classmethod
    def merge_graphs(cls, graphs: list["Graph"]) -> "Graph":
        """Merge multiple graphs into one."""
        all_nodes: list[Entity] = []
        all_edges: list[Edge] = []
        for graph in graphs:
            all_nodes.extend(graph.nodes)
            all_edges.extend(graph.edges)
        return cls(nodes=all_nodes, edges=all_edges)


__all__ = ["Graph"]
