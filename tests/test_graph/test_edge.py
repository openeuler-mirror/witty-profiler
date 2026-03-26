import unittest

from anansi.common.id_manager import GlobalIDManager
from anansi.edge.edge import DirectedEdge, EdgeFactory, UndirectedEdge
from anansi.entity.node_entity import ProcessEntity


def _reset_global_id_manager():
    GlobalIDManager._instance = None
    GlobalIDManager._global_id_map = {}


class TestEdge(unittest.TestCase):
    def setUp(self):
        _reset_global_id_manager()

    def test_directed_edge_global_id_and_nodes(self):
        src = ProcessEntity(pid=1)
        dst = ProcessEntity(pid=2)

        edge = EdgeFactory.get_instance().create_edge(
            {
                "edge_type": "DirectedEdge",
                "source_node": src,
                "target_node": dst,
            }
        )

        self.assertIsInstance(edge, DirectedEdge)
        self.assertIs(edge.source_node, src)
        self.assertIs(edge.target_node, dst)
        self.assertEqual(edge.nodes, [edge.source_node, edge.target_node])

    def test_create_edge_ensure_unique_reuses_same_instance(self):
        data = {
            "edge_type": "DirectedEdge",
            "source_node": ProcessEntity(pid=10),
            "target_node": ProcessEntity(pid=20),
        }

        factory = EdgeFactory.get_instance()
        first = factory.create_edge(data, ensure_unique=True)
        second = factory.create_edge(data, ensure_unique=True)

        self.assertIs(first, second)

    def test_undirected_edge_nodes_preserved(self):
        n1 = ProcessEntity(pid=100)
        n2 = ProcessEntity(pid=200)

        edge: UndirectedEdge = EdgeFactory.get_instance().create_edge(
            {"edge_type": "UndirectedEdge", "nodes": [n1, n2]}
        )

        self.assertIsInstance(edge, UndirectedEdge)
        self.assertEqual(len(edge.nodes), 2)
        self.assertIn(n1, edge.nodes)
        self.assertIn(n2, edge.nodes)


class TestEdgeEx(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.process1 = ProcessEntity(pid=3001)
        self.process2 = ProcessEntity(pid=3002)
        self.factory = EdgeFactory.get_instance()

    def test_edge_creation(self):
        """Test basic edge creation."""
        edge = UndirectedEdge(nodes=[self.process1, self.process2])

        self.assertEqual(edge.edge_type, "UndirectedEdge")
        self.assertEqual(len(edge.nodes), 2)
        self.assertIn(self.process1, edge.nodes)
        self.assertIn(self.process2, edge.nodes)
        self.assertIs(edge, EdgeFactory.get_instance().create_edge(edge))

    def test_directed_edge_creation(self):
        """Test directed edge creation."""
        edge = DirectedEdge(source_node=self.process1, target_node=self.process2)

        self.assertEqual(edge.edge_type, "DirectedEdge")
        self.assertEqual(edge.source_node, self.process1)
        self.assertEqual(edge.target_node, self.process2)
        self.assertEqual(len(edge.nodes), 2)
        self.assertIn(self.process1, edge.nodes)
        self.assertIn(self.process2, edge.nodes)

    def test_edge_global_id(self):
        """Test global ID generation for edges."""
        edge = UndirectedEdge(nodes=[self.process1, self.process2])
        expected_id = f"[UndirectedEdge]{[node.global_id for node in edge.nodes]}"

        self.assertEqual(edge.global_id, expected_id)

    def test_directed_edge_global_id(self):
        """Test global ID generation for directed edges."""
        edge = DirectedEdge(source_node=self.process1, target_node=self.process2)
        expected_id = (
            f"[DirectedEdge]{self.process1.global_id}→{self.process2.global_id}"
        )

        self.assertEqual(edge.global_id, expected_id)

    def test_edge_model_dump(self):
        """Test model dump functionality for edges."""
        edge = UndirectedEdge(nodes=[self.process1, self.process2])
        result = edge.model_dump()

        self.assertIsInstance(result, dict)
        self.assertIn("nodes", result)
        self.assertIn("edge_type", result)
        self.assertEqual(result["edge_type"], "UndirectedEdge")

    def test_edge_factory_creation(self):
        """Test creating edges using the factory."""
        edge_data = {
            "edge_type": "UndirectedEdge",
            "nodes": [{"entity_type": "ProcessEntity", "pid": 4001}],
        }

        edge = self.factory.create_edge(edge_data)
        self.assertIsInstance(edge, UndirectedEdge)

    def test_directed_edge_factory_creation(self):
        """Test creating directed edges using the factory."""
        edge_data = {
            "edge_type": "DirectedEdge",
            "source_node": {"entity_type": "ProcessEntity", "pid": 5001},
            "target_node": {"entity_type": "ProcessEntity", "pid": 5002},
        }

        edge = self.factory.create_edge(edge_data)
        self.assertIsInstance(edge, DirectedEdge)

    def test_factory_get_instance(self):
        """Test singleton pattern for EdgeFactory."""
        factory1 = EdgeFactory.get_instance()
        factory2 = EdgeFactory.get_instance()

        self.assertIs(factory1, factory2)

    def test_invalid_edge_type(self):
        """Test that creating an unknown edge type raises an error."""
        invalid_data = {"edge_type": "InvalidEdgeType", "nodes": []}

        with self.assertRaises(ValueError):
            self.factory.hard_create_edge(invalid_data)


if __name__ == "__main__":
    unittest.main()
