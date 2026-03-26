import unittest

from witty_profiler.edge.edge import DirectedEdge, UndirectedEdge
from witty_profiler.entity.node_entity import ProcessEntity, ThreadEntity
from witty_profiler.graph.graph import Graph


class TestGraph(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.graph = Graph()

        # Create some test entities
        self.process1 = ProcessEntity(pid=1001)
        self.process2 = ProcessEntity(pid=1002)
        self.thread1 = ThreadEntity(tid=5001, process=self.process1)
        self.thread2 = ThreadEntity(tid=5002, process=self.process2)

    def test_initialization_empty(self):
        """Test initialization of empty graph."""
        g = Graph()
        self.assertEqual(len(g.nodes), 0)
        self.assertEqual(len(g.edges), 0)

    def test_add_node(self):
        """Test adding a node to the graph."""
        initial_count = len(self.graph.nodes)
        self.graph.try_add_node(self.process1)

        self.assertEqual(len(self.graph.nodes), initial_count + 1)
        self.assertIn(self.process1, self.graph.nodes)
        self.assertIn(self.process1.global_id, self.graph._id2nodes)

    def test_add_existing_node(self):
        """Test that adding an existing node doesn't duplicate it."""
        self.graph.try_add_node(self.process1)
        initial_count = len(self.graph.nodes)

        # Try to add the same node again
        self.graph.try_add_node(self.process1)

        # Count should remain the same
        self.assertEqual(len(self.graph.nodes), initial_count)

    def test_add_edge(self):
        """Test adding an edge to the graph."""
        edge = DirectedEdge(source_node=self.process1, target_node=self.process2)
        initial_node_count = len(self.graph.nodes)
        initial_edge_count = len(self.graph.edges)

        self.graph.try_add_edge(edge)

        # Both nodes should now be in the graph
        self.assertEqual(len(self.graph.nodes), initial_node_count + 2)
        self.assertEqual(len(self.graph.edges), initial_edge_count + 1)
        self.assertIn(edge, self.graph.edges)

    def test_model_dump(self):
        """Test model dump functionality."""
        self.graph.try_add_node(self.process1)
        result = self.graph.model_dump()

        self.assertIsInstance(result, dict)
        self.assertIn("nodes", result)
        self.assertIn("edges", result)

    def test_describe(self):
        """Test the describe method."""
        self.graph.try_add_node(self.process1)
        self.graph.try_add_node(self.process2)

        description = self.graph.describe()
        self.assertIn("Graph with 2 nodes", description)
        self.assertIn("ProcessEntity(pid=1001", description)
        self.assertIn("ProcessEntity(pid=1002", description)

    def test_graph_equality(self):
        """Test graph equality comparison."""
        g1 = Graph(nodes=[self.process1, self.process2])
        g2 = Graph(nodes=[self.process1, self.process2])
        edge1 = DirectedEdge(source_node=self.process1, target_node=self.process2)
        edge2 = UndirectedEdge(nodes=[self.process1, self.process2])
        g3 = Graph(nodes=[self.process1, self.process2], edges=[edge1])
        g4 = Graph(nodes=[self.process1, self.process2], edges=[edge2])
        g5 = Graph(nodes=[self.process1, self.process2], edges=[edge2])

        # Since they have the same nodes but no edges, they should be equal
        self.assertEqual(g1, g2)
        self.assertNotEqual(g1, g3)
        self.assertNotEqual(g3, g4)
        self.assertEqual(g4, g5)
        self.assertNotEqual(g1, self.process1)
        self.assertNotEqual(self.process1, g1)

    def test_graph_comparison_ge(self):
        """Test greater than or equal comparison."""
        g1 = Graph(nodes=[self.process1])
        g2 = Graph(nodes=[self.process1, self.process2])
        # g2 contains all nodes from g1, so g2 >= g1
        self.assertTrue(g2 >= g1)
        self.assertFalse(g1 >= g2)

        with self.assertRaises(RuntimeError) as cm:
            exp = g1 >= self.process1
        cm.exception.args[0] == "Can only compare with another Graph"

    def test_graph_comparison_le(self):
        """Test less than or equal comparison."""
        g1 = Graph(nodes=[self.process1])
        g2 = Graph(nodes=[self.process1, self.process2])

        # g1 contains fewer nodes than g2, so g1 <= g2
        self.assertTrue(g1 <= g2)
        self.assertFalse(g2 <= g1)

        with self.assertRaises(RuntimeError) as cm:
            exp = g1 <= self.process1

    def test_graph_edge_with_extra_nodes(self):
        """Test edge with extra nodes."""
        extra_process = ProcessEntity(pid=2001)
        edge1 = UndirectedEdge(nodes=[self.process1, self.process2])
        edge2 = UndirectedEdge(nodes=[self.process1, extra_process])
        graph = Graph(nodes=[self.process1, self.process2], edges=[edge1, edge2])
        self.assertIn(extra_process, graph.nodes)


if __name__ == "__main__":
    unittest.main()
