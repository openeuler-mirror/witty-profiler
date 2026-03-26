import unittest

from anansi.edge.edge_category import DataStreamEdge, DeployEdgeP2C
from anansi.entity.node_entity import (
    ProcessEntity,
    SharedMemoryEntity,
    SocketEntity,
    ThreadEntity,
)
from anansi.graph.graph import Graph
from anansi.visualize.layout.implementations.min_crossing_layout import (
    MinCrossingLayout,
)
from anansi.visualize.renderer import DrawioRenderer, HtmlRenderer
from anansi.visualize.renderer.default_renderer import DefaultLayoutRenderer
from anansi.visualize.renderer.renderer_base import (
    available_renderers,
    get_renderer_class,
)


class TestVisualizeLayout(unittest.TestCase):

    def _walk(self, root):
        stack = [root]
        out = []
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(node.deploy_children.values())
        return out

    def test_default_layout_assigns_xywh(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        p2 = ProcessEntity(pid=1002, ppid=1)
        t1 = ThreadEntity(tid=2001, process=p1)
        t2 = ThreadEntity(tid=2002, process=p1)

        graph = Graph(
            nodes=[p1, p2, t1, t2],
            edges=[
                DeployEdgeP2C(source_node=p1, target_node=t1),
                DeployEdgeP2C(source_node=p1, target_node=t2),
                DataStreamEdge(source_node=t1, target_node=t2),
                DataStreamEdge(source_node=p1, target_node=p2),
            ],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        all_nodes = self._walk(layout.root)

        # Root should be anchored at origin in grid units.
        self.assertEqual(layout.root.x, 0)
        self.assertEqual(layout.root.y, 0)

        for node in all_nodes:
            self.assertIsNotNone(node.x)
            self.assertIsNotNone(node.y)
            self.assertIsNotNone(node.w)
            self.assertIsNotNone(node.h)
            self.assertGreaterEqual(node.w, 0)
            self.assertGreaterEqual(node.h, 0)

        # Every child must be inside the parent box.
        for parent in all_nodes:
            for child in parent.deploy_children.values():
                self.assertGreaterEqual(child.x, parent.x)
                self.assertGreaterEqual(child.y, parent.y)
                self.assertLessEqual(child.x + child.w, parent.x + parent.w)
                self.assertLessEqual(child.y + child.h, parent.y + parent.h)

    def test_default_renderer_contains_geometry(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        p2 = ProcessEntity(pid=1002, ppid=1)
        graph = Graph(
            nodes=[p1, p2],
            edges=[DataStreamEdge(source_node=p1, target_node=p2)],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        output = DefaultLayoutRenderer(layout=layout).render()

        self.assertIn("x=", output)
        self.assertIn("y=", output)
        self.assertIn("w=", output)
        self.assertIn("h=", output)

    def test_html_renderer_generates_html_document(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        p2 = ProcessEntity(pid=1002, ppid=1)
        graph = Graph(
            nodes=[p1, p2],
            edges=[DataStreamEdge(source_node=p1, target_node=p2)],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        renderer_cls = get_renderer_class("html")
        self.assertIsNotNone(renderer_cls)
        output = renderer_cls(layout=layout).render()

        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("<svg", output)
        self.assertIn("<rect", output)
        self.assertIn("<line", output)

    def test_drawio_renderer_generates_mxfile(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        p2 = ProcessEntity(pid=1002, ppid=1)
        graph = Graph(
            nodes=[p1, p2],
            edges=[DataStreamEdge(source_node=p1, target_node=p2)],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        renderer_cls = get_renderer_class("drawio")
        self.assertIsNotNone(renderer_cls)
        output = renderer_cls(layout=layout).render()

        self.assertIn("<mxfile", output)
        self.assertIn("<mxGraphModel", output)
        self.assertIn('vertex="1"', output)
        self.assertIn('edge="1"', output)

    def test_available_renderers_exposes_html_and_drawio(self):
        all_renderers = set(available_renderers())
        self.assertIn("default", all_renderers)
        self.assertIn("html", all_renderers)
        self.assertIn("drawio", all_renderers)

    def test_original_data_stream_edges_are_preserved(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        t1 = ThreadEntity(tid=2001, process=p1)
        t2 = ThreadEntity(tid=2002, process=p1)

        graph = Graph(
            nodes=[p1, t1, t2],
            edges=[
                DeployEdgeP2C(source_node=p1, target_node=t1),
                DeployEdgeP2C(source_node=p1, target_node=t2),
                DataStreamEdge(source_node=t1, target_node=t2),
            ],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        all_nodes = self._walk(layout.root)
        by_gid = {
            node.entity.global_id: node
            for node in all_nodes
            if node.entity is not None and hasattr(node.entity, "global_id")
        }

        t1_layout = by_gid[t1.global_id]
        t2_layout = by_gid[t2.global_id]
        p1_layout = by_gid[p1.global_id]

        # Original thread-to-thread edge must be preserved for rendering.
        self.assertIn(id(t2_layout), t1_layout.real_data_stream_children)

        # Derived process-level relation may exist for layout decisions,
        # but should not be treated as original stream edge.
        self.assertEqual(p1_layout.real_data_stream_children, {})

    def test_renderers_use_only_real_edges_when_available(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        t1 = ThreadEntity(tid=2001, process=p1)
        t2 = ThreadEntity(tid=2002, process=p1)

        graph = Graph(
            nodes=[p1, t1, t2],
            edges=[
                DeployEdgeP2C(source_node=p1, target_node=t1),
                DeployEdgeP2C(source_node=p1, target_node=t2),
                DataStreamEdge(source_node=t1, target_node=t2),
            ],
        )

        layout = MinCrossingLayout().build_from_graph(graph)

        html_edges = HtmlRenderer(layout=layout)._collect_edges()
        drawio_nodes = DrawioRenderer(layout=layout)._collect_nodes()
        drawio_edges = DrawioRenderer(layout=layout)._collect_edges(drawio_nodes)

        # Should only keep the original t1 -> t2 edge and avoid derived edges.
        self.assertEqual(len(html_edges), 1)
        self.assertEqual(len(drawio_edges), 1)
        self.assertNotEqual(id(html_edges[0][0]), id(html_edges[0][1]))
        self.assertNotEqual(id(drawio_edges[0][0]), id(drawio_edges[0][1]))

    def test_same_type_resources_are_grouped_under_synthetic_parent(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        shm1 = SharedMemoryEntity(shm_name="/anansi/a", shm_size=1024)
        shm2 = SharedMemoryEntity(shm_name="/anansi/b", shm_size=2048)

        graph = Graph(
            nodes=[p1, shm1, shm2],
            edges=[
                DeployEdgeP2C(source_node=p1, target_node=shm1),
                DeployEdgeP2C(source_node=p1, target_node=shm2),
            ],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        all_nodes = self._walk(layout.root)
        by_gid = {
            node.entity.global_id: node
            for node in all_nodes
            if node.entity is not None and hasattr(node.entity, "global_id")
        }

        shm1_layout = by_gid[shm1.global_id]
        shm2_layout = by_gid[shm2.global_id]
        self.assertIs(shm1_layout.deploy_parent, shm2_layout.deploy_parent)
        self.assertIsNotNone(shm1_layout.deploy_parent)
        self.assertEqual(
            shm1_layout.deploy_parent.entity,
            "ResourceGroup:SharedMemoryEntity",
        )

    def test_non_resource_children_are_grouped_under_common_parent(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        t1 = ThreadEntity(tid=2001, process=p1)
        t2 = ThreadEntity(tid=2002, process=p1)

        graph = Graph(
            nodes=[p1, t1, t2],
            edges=[
                DeployEdgeP2C(source_node=p1, target_node=t1),
                DeployEdgeP2C(source_node=p1, target_node=t2),
            ],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        all_nodes = self._walk(layout.root)
        by_gid = {
            node.entity.global_id: node
            for node in all_nodes
            if node.entity is not None and hasattr(node.entity, "global_id")
        }

        t1_layout = by_gid[t1.global_id]
        t2_layout = by_gid[t2.global_id]
        self.assertIs(t1_layout.deploy_parent, t2_layout.deploy_parent)
        self.assertIsNotNone(t1_layout.deploy_parent)
        self.assertEqual(
            t1_layout.deploy_parent.entity,
            "NonResourceGroup:Common",
        )

    def test_socket_children_are_grouped_under_socket_group(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        t1 = ThreadEntity(tid=2001, process=p1)
        s1 = SocketEntity(socket_addr="127.0.0.1", socket_port=8080)
        s2 = SocketEntity(socket_addr="127.0.0.1", socket_port=8081)

        graph = Graph(
            nodes=[p1, t1, s1, s2],
            edges=[
                DeployEdgeP2C(source_node=p1, target_node=t1),
                DeployEdgeP2C(source_node=t1, target_node=s1),
                DeployEdgeP2C(source_node=t1, target_node=s2),
            ],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        all_nodes = self._walk(layout.root)
        by_gid = {
            node.entity.global_id: node
            for node in all_nodes
            if node.entity is not None and hasattr(node.entity, "global_id")
        }

        s1_layout = by_gid[s1.global_id]
        s2_layout = by_gid[s2.global_id]
        self.assertIs(s1_layout.deploy_parent, s2_layout.deploy_parent)
        self.assertEqual(s1_layout.deploy_parent.entity, "SocketGroup:Common")
        self.assertIsNotNone(s1_layout.deploy_parent.deploy_parent)
        self.assertEqual(
            s1_layout.deploy_parent.deploy_parent.entity.global_id, t1.global_id
        )

    def test_html_renderer_renders_socket_as_circle(self):
        p1 = ProcessEntity(pid=1001, ppid=1)
        s1 = SocketEntity(socket_addr="127.0.0.1", socket_port=8080)
        graph = Graph(
            nodes=[p1, s1],
            edges=[DeployEdgeP2C(source_node=p1, target_node=s1)],
        )

        layout = MinCrossingLayout().build_from_graph(graph)
        output = HtmlRenderer(layout=layout).render()
        self.assertIn('<circle class="node socket-node"', output)


if __name__ == "__main__":
    unittest.main()
