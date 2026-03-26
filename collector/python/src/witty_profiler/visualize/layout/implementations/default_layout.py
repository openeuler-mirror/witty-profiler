import json
from typing import Optional

import networkx as nx

from witty_profiler.common.logging import get_logger
from witty_profiler.edge.edge_category import (
    DataStreamEdge,
    DeployEdgeC2P,
    DeployEdgeP2C,
    DirectedEdge,
)
from witty_profiler.entity.node_entity import (
    ProcessEntity,
    ResourceEntity,
    SocketEntity,
    ThreadEntity,
)
from witty_profiler.graph.graph import Graph
from witty_profiler.visualize.layout.layout_element import LayoutElement

from ..layout import Layout, LayoutElement
from .gridifier import Gridifier

LOGGER = get_logger(__name__)


class SetTupleEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, tuple):
            return list(obj)
        return super().default(obj)


class DefaultLayout(Layout):

    LEAF_MIN_WIDTH = 4
    LEAF_MIN_HEIGHT = 2
    CELL_GAP_X = 1
    CELL_GAP_Y = 1
    PADDING_X = 1
    PADDING_Y = 1
    TITLE_HEIGHT = 1
    SOCKET_MIN_WIDTH = 1
    SOCKET_MIN_HEIGHT = 1

    def __init__(self):
        super().__init__()

    def build_from_graph(self, graph: Graph) -> Layout:
        """
        Build the layout from a given graph. This method will create LayoutElements for each entity
        in the graph and establish parent-child relationships based on the edges.
        """

        id_to_layout_elements: dict[int, LayoutElement] = {}
        entity_id_to_layout_element: dict[str, LayoutElement] = {}

        # 分配初层LayoutElement
        for node in graph.nodes:
            layout_element = LayoutElement(
                entity=node,
                deploy_parent=self.root,  # 默认所有元素的父元素是root，后续根据部署关系调整
            )
            self.root.add_deploy_child(layout_element)  # 将元素添加到root的部署子元素中
            id_to_layout_elements[id(layout_element)] = layout_element
            entity_id_to_layout_element[node.global_id] = layout_element
        # 根据边进行关系分配
        # 部署分配 （DeployEdgeC2P, DeployEdgeP2C等）建立父子关系
        unused_edges: dict[str, set] = dict()
        used_deploy_edges: dict[str, set] = dict()
        # 线程到进程
        for node in graph.nodes:
            if isinstance(node, ThreadEntity):
                thread_le = entity_id_to_layout_element.get(node.global_id)
                process_le = entity_id_to_layout_element.get(node.process.global_id)
                if process_le and thread_le:
                    process_le.add_deploy_child(thread_le)
        # 根据边关系
        for edge in graph.edges:
            if isinstance(edge, (DeployEdgeC2P, DeployEdgeP2C)):
                used_deploy_edges.setdefault(edge.edge_type, set()).add(
                    "{} → {}".format(
                        edge.source_node.entity_type, edge.target_node.entity_type
                    )
                )
                source_layout_element = entity_id_to_layout_element[
                    edge.source_node.global_id
                ]
                target_layout_element = entity_id_to_layout_element[
                    edge.target_node.global_id
                ]
                # 建立父子关系
                if isinstance(edge, DeployEdgeP2C):
                    parent_element = source_layout_element
                    child_element = target_layout_element
                else:  # DeployEdgeC2P
                    parent_element = target_layout_element
                    child_element = source_layout_element
                parent_element.add_deploy_child(child_element)
            elif isinstance(edge, DirectedEdge):
                unused_edges.setdefault(edge.edge_type, set()).add(
                    "{} → {}".format(
                        edge.source_node.entity_type, edge.target_node.entity_type
                    )
                )
        LOGGER.info(
            "used edge types in layout building: %s",
            json.dumps(
                used_deploy_edges, cls=SetTupleEncoder, indent=2, ensure_ascii=False
            ),
        )
        LOGGER.info(
            "unused edge types in layout building: %s",
            json.dumps(unused_edges, cls=SetTupleEncoder, indent=2, ensure_ascii=False),
        )

        # Group same ResourceEntity subclasses under synthetic category parents,
        # then reuse the existing deploy/layout pipeline.
        self._group_resource_children_by_type(self.root)

        self.root.allocate_layout_depth_top_down(0)

        # 数据流分配（DataStreamEdge）建立连接关系
        for edge in graph.edges:
            if isinstance(edge, DataStreamEdge):
                source_layout_element = entity_id_to_layout_element[
                    edge.source_node.global_id
                ]
                target_layout_element = entity_id_to_layout_element[
                    edge.target_node.global_id
                ]
                # Keep a copy of the original stream edge for renderer usage.
                source_layout_element.add_real_data_stream_child(target_layout_element)
                # Process层级关系
                source_process_layout = self.find_process_layout(source_layout_element)
                target_process_layout = self.find_process_layout(target_layout_element)
                if (
                    source_process_layout is not None
                    and target_process_layout is not None
                ):
                    # Process Data Stream
                    final_source_element_layout = source_process_layout
                    final_target_element_layout = target_process_layout
                elif source_process_layout is not None:
                    # Process Access Resource
                    final_source_element_layout = source_process_layout
                    final_target_element_layout = target_layout_element
                elif target_process_layout is not None:
                    raise NotImplementedError(
                        "Resource to Process Relationship not supported yet"
                    )
                else:
                    # Resource to Resource Data Stream, treat them as being in the same process
                    final_source_element_layout = source_layout_element
                    final_target_element_layout = target_layout_element
                final_source_element_layout.add_data_stream_child(
                    final_target_element_layout
                )
                # Propagate data stream to parent elemnents in both sides
                while (
                    final_source_element_layout.depth
                    > final_target_element_layout.depth
                ):
                    final_source_element_layout = (
                        final_source_element_layout.deploy_parent
                    )
                    final_source_element_layout.add_data_stream_child(
                        final_target_element_layout
                    )
                while (
                    final_target_element_layout.depth
                    > final_source_element_layout.depth
                ):
                    final_target_element_layout = (
                        final_target_element_layout.deploy_parent
                    )
                    final_source_element_layout.add_data_stream_child(
                        final_target_element_layout
                    )
                while final_source_element_layout != final_target_element_layout:
                    parent_src = final_source_element_layout.deploy_parent
                    parent_tgt = final_target_element_layout.deploy_parent
                    if (
                        not parent_src.is_root
                        and not parent_tgt.is_root
                        and parent_src != parent_tgt
                    ):
                        parent_src.add_data_stream_child(parent_tgt)
                    else:
                        break
                    final_source_element_layout = parent_src
                    final_target_element_layout = parent_tgt
        # 根据数据流关系设置部署元素内子元素的相对布局位置
        self.allocate_ralative_pos(self.root)
        # 根据相对位置大小，自底向上统计得到各个元素的大小
        self.compute_size_bottom_up(self.root)
        # 自顶向下分配绝对坐标
        self.allocate_abs_pos_top_down(self.root, 0, 0)
        return self

    def find_process_layout(
        self, layout_element: LayoutElement
    ) -> Optional[LayoutElement]:
        """在当前元素的部署关系树中寻找Process类型的元素"""
        if layout_element.entity and isinstance(layout_element.entity, ProcessEntity):
            return layout_element
        while layout_element.deploy_parent:
            layout_element = layout_element.deploy_parent
            if layout_element.entity and isinstance(
                layout_element.entity, ProcessEntity
            ):
                return layout_element
        return None

    def allocate_ralative_pos(self, layout_element: LayoutElement):
        """根据部署关系树和数据流关系为元素分配相对布局位置。"""
        direct_deploy_children = list(layout_element.deploy_children.values())
        if not direct_deploy_children:
            layout_element._children_relative_pos = {}
            layout_element._children_local_offset = {}
            return

        direct_deploy_children_id_set = set(id(e) for e in direct_deploy_children)
        # 根据direct_deploy_children之间的数据流关系进行布局，首先提取出这些节点之间的边
        direct_data_stream_edges = []
        for child in direct_deploy_children:
            for data_stream_child in child.data_stream_children.values():
                if id(data_stream_child) in direct_deploy_children_id_set:
                    direct_data_stream_edges.append((id(child), id(data_stream_child)))
        # 根据连接关系，找出布局方式
        layout = self.layout_parent_higher_than_child(
            set(direct_deploy_children_id_set), direct_data_stream_edges
        )
        layout = Gridifier.gridify_with_conflict_resolution(layout)

        # Normalize to a non-negative local grid coordinate system.
        if layout:
            min_x = min(v[0] for v in layout.values())
            min_y = min(v[1] for v in layout.values())
            layout = {
                node_id: (int(x - min_x), int(y - min_y))
                for node_id, (x, y) in layout.items()
            }
        else:
            # Fallback when graph layout returns nothing.
            layout = {
                id(child): (idx, 0) for idx, child in enumerate(direct_deploy_children)
            }

        layout_element._children_relative_pos = layout
        for child in direct_deploy_children:
            self.allocate_ralative_pos(child)

    def _group_resource_children_by_type(self, parent: LayoutElement):
        """Insert synthetic parents for resource/non-resource child groups."""
        if isinstance(parent.entity, str) and (
            parent.entity.startswith("ResourceGroup:")
            or parent.entity.startswith("NonResourceGroup:")
            or parent.entity.startswith("SocketGroup:")
        ):
            return

        children = list(parent.deploy_children.values())
        grouped: dict[type, list[LayoutElement]] = {}
        for child in children:
            if child.entity is not None and isinstance(child.entity, ResourceEntity):
                grouped.setdefault(type(child.entity), []).append(child)

        for resource_cls, resource_children in grouped.items():
            if len(resource_children) <= 1:
                continue

            group_node = LayoutElement(
                entity=f"ResourceGroup:{resource_cls.__name__}",
                deploy_parent=parent,
            )
            parent.add_deploy_child(group_node)
            for child in resource_children:
                group_node.add_deploy_child(child)

        # For process/thread, put all SocketEntity children under one socket group.
        if parent.entity is not None and isinstance(
            parent.entity, (ProcessEntity, ThreadEntity)
        ):
            socket_children = [
                child
                for child in children
                if child.entity is not None and isinstance(child.entity, SocketEntity)
            ]
            if socket_children:
                group_node = LayoutElement(
                    entity="SocketGroup:Common",
                    deploy_parent=parent,
                )
                parent.add_deploy_child(group_node)
                for child in socket_children:
                    group_node.add_deploy_child(child)

        def is_synthetic_group(child: LayoutElement) -> bool:
            return isinstance(child.entity, str) and (
                child.entity.startswith("ResourceGroup:")
                or child.entity.startswith("NonResourceGroup:")
                or child.entity.startswith("SocketGroup:")
            )

        non_resource_children = [
            child
            for child in children
            if (child.entity is None or not isinstance(child.entity, ResourceEntity))
            and not is_synthetic_group(child)
            and not (
                child.entity is not None and isinstance(child.entity, SocketEntity)
            )
        ]
        if len(non_resource_children) > 1:
            group_node = LayoutElement(
                entity="NonResourceGroup:Common",
                deploy_parent=parent,
            )
            parent.add_deploy_child(group_node)
            for child in non_resource_children:
                group_node.add_deploy_child(child)

        for child in list(parent.deploy_children.values()):
            self._group_resource_children_by_type(child)

    def compute_size_bottom_up(self, layout_element: LayoutElement):
        """Compute each node's width/height and local child offsets bottom-up."""
        direct_children = list(layout_element.deploy_children.values())
        if not direct_children:
            if layout_element.is_root:
                layout_element.w = 0
                layout_element.h = 0
            else:
                if layout_element.entity is not None and isinstance(
                    layout_element.entity, SocketEntity
                ):
                    layout_element.w = self.SOCKET_MIN_WIDTH
                    layout_element.h = self.SOCKET_MIN_HEIGHT
                else:
                    layout_element.w = self.LEAF_MIN_WIDTH
                    layout_element.h = self.LEAF_MIN_HEIGHT
            layout_element._children_local_offset = {}
            return

        for child in direct_children:
            self.compute_size_bottom_up(child)

        relative_pos = layout_element._children_relative_pos or {}
        if not relative_pos:
            relative_pos = {
                id(child): (idx, 0) for idx, child in enumerate(direct_children)
            }
            layout_element._children_relative_pos = relative_pos

        child_by_id = {id(child): child for child in direct_children}
        cols = sorted({int(relative_pos[id(child)][0]) for child in direct_children})
        rows = sorted({int(relative_pos[id(child)][1]) for child in direct_children})

        col_widths = {
            col: max(
                child_by_id[node_id].w
                for node_id, (x, _) in relative_pos.items()
                if int(x) == col and node_id in child_by_id
            )
            for col in cols
        }
        row_heights = {
            row: max(
                child_by_id[node_id].h
                for node_id, (_, y) in relative_pos.items()
                if int(y) == row and node_id in child_by_id
            )
            for row in rows
        }

        title_height = 0 if layout_element.is_root else self.TITLE_HEIGHT
        col_origin: dict[int, int] = {}
        row_origin: dict[int, int] = {}

        cursor_x = self.PADDING_X
        for col in cols:
            col_origin[col] = cursor_x
            cursor_x += col_widths[col] + self.CELL_GAP_X

        cursor_y = title_height + self.PADDING_Y
        for row in rows:
            row_origin[row] = cursor_y
            cursor_y += row_heights[row] + self.CELL_GAP_Y

        local_offsets: dict[int, tuple[int, int]] = {}
        max_right = 0
        max_bottom = 0
        for child in direct_children:
            child_id = id(child)
            grid_x, grid_y = relative_pos.get(child_id, (0, 0))
            local_x = col_origin[int(grid_x)]
            local_y = row_origin[int(grid_y)]
            local_offsets[child_id] = (local_x, local_y)
            max_right = max(max_right, local_x + int(child.w or 0))
            max_bottom = max(max_bottom, local_y + int(child.h or 0))

        layout_element._children_local_offset = local_offsets
        layout_element.w = max(self.LEAF_MIN_WIDTH, max_right + self.PADDING_X)
        layout_element.h = max(
            title_height + self.PADDING_Y * 2,
            max_bottom + self.PADDING_Y,
            self.LEAF_MIN_HEIGHT,
        )

    def allocate_abs_pos_top_down(
        self, layout_element: LayoutElement, abs_x: int, abs_y: int
    ):
        """Allocate absolute x/y coordinates top-down in grid units."""
        layout_element.x = abs_x
        layout_element.y = abs_y

        for child in layout_element.deploy_children.values():
            local_x, local_y = layout_element._children_local_offset.get(
                id(child), (self.PADDING_X, self.PADDING_Y)
            )
            self.allocate_abs_pos_top_down(child, abs_x + local_x, abs_y + local_y)

    def layout_parent_higher_than_child(
        self, V: set[int], E: list[tuple[int, int]]
    ) -> dict[int, tuple[float, float]]:
        """
        allocate (row, col) for each node in V
        such that for each edge (A, B) in E, A.row < B.row
        for all children of the same parent, try to put them in different cols to avoid overlap,
            if not possible, put them in the same col but different rows.
        """
        if not V:
            return {}

        # Build directed graph from valid in-scope edges.
        digraph = nx.DiGraph()
        digraph.add_nodes_from(V)
        for src, dst in E:
            if src in V and dst in V and src != dst:
                digraph.add_edge(src, dst)

        if digraph.number_of_edges() == 0:
            ordered_nodes = sorted(V)
            return {node: (float(col), 0.0) for col, node in enumerate(ordered_nodes)}

        # Condense SCCs to a DAG and compute row by longest-path layering.
        sccs = list(nx.strongly_connected_components(digraph))
        node_to_component: dict[int, int] = {}
        for component_id, component_nodes in enumerate(sccs):
            for node in component_nodes:
                node_to_component[node] = component_id

        component_graph = nx.DiGraph()
        component_graph.add_nodes_from(range(len(sccs)))
        for src, dst in digraph.edges():
            src_comp = node_to_component[src]
            dst_comp = node_to_component[dst]
            if src_comp != dst_comp:
                component_graph.add_edge(src_comp, dst_comp)

        component_row: dict[int, int] = {
            comp_id: 0 for comp_id in component_graph.nodes()
        }
        for comp_id in nx.topological_sort(component_graph):
            base_row = component_row[comp_id]
            for child_comp in component_graph.successors(comp_id):
                component_row[child_comp] = max(component_row[child_comp], base_row + 1)

        row_by_node: dict[int, int] = {}
        for component_id, component_nodes in enumerate(sccs):
            base_row = component_row.get(component_id, 0)
            # Nodes inside an SCC cannot all satisfy strict ordering; spread them
            # deterministically across adjacent rows to keep a stable layout.
            for row_offset, node in enumerate(sorted(component_nodes)):
                row_by_node[node] = base_row + row_offset

        rows: dict[int, list[int]] = {}
        for node in V:
            row = row_by_node.get(node, 0)
            rows.setdefault(row, []).append(node)

        # Barycenter ordering: for each row, place nodes close to predecessor cols.
        # This tends to reduce edge crossing while keeping columns unique in a row.
        pos: dict[int, tuple[float, float]] = {}
        for row in sorted(rows):
            nodes = rows[row]
            if row == 0:
                ordered = sorted(nodes)
            else:

                def sort_key(node: int) -> tuple[float, int]:
                    preds = [pred for pred in digraph.predecessors(node) if pred in pos]
                    if not preds:
                        return (float("inf"), node)
                    barycenter = sum(pos[pred][0] for pred in preds) / len(preds)
                    return (barycenter, node)

                ordered = sorted(nodes, key=sort_key)

            for col, node in enumerate(ordered):
                pos[node] = (float(col), float(row))

        for missing_node in V:
            pos.setdefault(missing_node, (0.0, 0.0))

        return pos


__all__ = ["DefaultLayout"]
