import unittest

from anansi.collector.local_collector.common_parent_collector import (
    CommonProcessParentCollector,
)
from anansi.entity.node_entity.node_entity import ProcessEntity, SocketEntity


class TestCommonProcessParentCollector(unittest.TestCase):
    def test_detects_common_parent_for_two_children(self):
        collector = CommonProcessParentCollector()

        child_a = ProcessEntity(pid=21001, ppid=31000)
        child_b = ProcessEntity(pid=21002, ppid=31000)

        neighbors_a, edges_a = collector.get_neighbors_with_edges(child_a)
        neighbors_b, edges_b = collector.get_neighbors_with_edges(child_b)

        self.assertEqual(neighbors_a, [])
        self.assertEqual(edges_a, [])
        self.assertEqual(edges_b, [])
        self.assertEqual(len(neighbors_b), 1)
        self.assertIsInstance(neighbors_b[0], ProcessEntity)
        self.assertEqual(neighbors_b[0].pid, 31000)

    def test_clear_resets_internal_state(self):
        collector = CommonProcessParentCollector()

        collector.get_neighbors_with_edges(ProcessEntity(pid=22001, ppid=32000))
        neighbors, _ = collector.get_neighbors_with_edges(
            ProcessEntity(pid=22002, ppid=32000)
        )
        self.assertEqual(len(neighbors), 1)

        collector.clear()

        collector.get_neighbors_with_edges(ProcessEntity(pid=22003, ppid=32000))
        neighbors_after_clear, _ = collector.get_neighbors_with_edges(
            ProcessEntity(pid=22004, ppid=32000)
        )
        self.assertEqual(len(neighbors_after_clear), 1)

    def test_non_process_input_returns_empty(self):
        collector = CommonProcessParentCollector()
        neighbors, edges = collector.get_neighbors_with_edges(
            SocketEntity(socket_port=18090)
        )
        self.assertEqual(neighbors, [])
        self.assertEqual(edges, [])


if __name__ == "__main__":
    unittest.main()
