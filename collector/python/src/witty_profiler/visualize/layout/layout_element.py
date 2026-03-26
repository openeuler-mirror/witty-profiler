from dataclasses import dataclass, field
from typing import Optional

from witty_profiler.common.logging import get_logger
from witty_profiler.edge.edge_category import DataStreamEdge, DeployEdge
from witty_profiler.entity.entity_base import Entity, EntityFactory
from witty_profiler.entity.node_entity import ResourceEntity

LOGGER = get_logger(__name__)


@dataclass
class LayoutElement:
    """an element in the layout, which represents a box in the graph"""

    is_root: bool = False  # 是否是根元素，根元素是整个图的容器

    data_stream_children: dict[int, "LayoutElement"] = field(
        default_factory=dict
    )  # 存在连接关系
    real_data_stream_children: dict[int, "LayoutElement"] = field(
        default_factory=dict
    )  # 原始图中的真实 data stream 连线
    deploy_children: dict[int, "LayoutElement"] = field(
        default_factory=dict
    )  # 存在部署关系，子元素在父元素的框图内
    deploy_parent: Optional["LayoutElement"] = field(
        default=None
    )  # 存在部署关系的父元素
    entity: Optional[Entity] = field(default=None)  # 关联的实体对象

    depth: Optional[int] = field(
        default=None
    )  # 布局深度，根元素为0，子元素为父元素深度+1

    _children_relative_pos: Optional[dict[int, tuple[float, float]]] = field(
        default=None
    )
    _children_local_offset: dict[int, tuple[int, int]] = field(default_factory=dict)

    # Geometry values in layout grid units.
    x: Optional[int] = field(default=None)
    y: Optional[int] = field(default=None)
    w: Optional[int] = field(default=None)
    h: Optional[int] = field(default=None)

    def add_data_stream_child(self, child: "LayoutElement"):
        self.data_stream_children[id(child)] = child

    def add_real_data_stream_child(self, child: "LayoutElement"):
        self.real_data_stream_children[id(child)] = child

    def add_deploy_child(self, child: "LayoutElement"):
        assert child.deploy_parent
        if child.deploy_parent:
            child.deploy_parent.remove_deploy_child(child)

        self.deploy_children[id(child)] = child
        child.deploy_parent = self

    def remove_deploy_child(self, child: "LayoutElement"):
        if id(child) in self.deploy_children:
            del self.deploy_children[id(child)]
            child.deploy_parent = None

    def root_deploy_ancestor(self) -> "LayoutElement":
        """返回当前元素所在的部署关系树的根元素"""
        current = self
        while current.deploy_parent:
            current = current.deploy_parent
        return current

    def allocate_layout_depth_top_down(self, depth: int = 0) -> int:
        self.depth = depth
        for c in self.deploy_children.values():
            c.allocate_layout_depth_top_down(depth + 1)

    def __str__(self):
        return "root" if self.is_root else f"[Depth={self.depth}] {self.entity}"

    def __stream_children_str__(self):
        return [str(e.entity) for e in self.data_stream_children.values()]


__all__ = ["LayoutElement"]
