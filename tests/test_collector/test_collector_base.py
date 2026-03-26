"""
Collector基类的单元测试
聚焦行为：BFS扩展、输入校验、注册表自动登记
"""

import unittest
import uuid

from anansi.collector.collector_base import Collector
from anansi.collector.local_collector import LocalCollector, get_local_collectors
from anansi.edge.edge import DirectedEdge, Edge
from anansi.entity.entity_base import Entity
from anansi.graph.graph import Graph


class DummyEntity(Entity):
    """简单的实体实现，用于测试"""

    identifier: str = ""

    @property
    def unique_id(self) -> str:
        return self.identifier


def new_entity(label: str) -> DummyEntity:
    # 使用随机后缀避免全局ID碰撞，测试间无需操作全局状态
    return DummyEntity(identifier=f"{label}_{uuid.uuid4().hex[:6]}")


def make_edge(src: Entity, dst: Entity) -> DirectedEdge:
    return DirectedEdge(source_node=src, target_node=dst)


class DummyCollector(Collector):
    """可配置邻居映射的Collector实现，便于验证BFS逻辑"""

    def __init__(
        self,
        neighbor_map: dict[str, tuple[list[Entity], list[Edge]]],
        seed_graph: Graph,
    ):
        self.neighbor_map = neighbor_map
        self.seed_graph = seed_graph

    def start(self):
        return None

    def stop(self):
        return None

    def clear(self):
        return None

    def _get_seed_graph(self) -> Graph:
        return self.seed_graph

    def get_neighbors_with_edges(self, entity: Entity):
        return self.neighbor_map.get(entity.global_id, ([], []))


class ExceptionCollector(DummyCollector):
    """在get_neighbors_with_edges阶段抛出异常的Collector"""

    def get_neighbors_with_edges(self, entity: Entity):
        raise OSError("neighbor lookup failed")


class TestCollectorBaseBFS(unittest.TestCase):
    def setUp(self):
        self.entity1 = new_entity("e1")
        self.entity2 = new_entity("e2")
        self.entity3 = new_entity("e3")

    def test_collect_since_traverses_neighbors_returns_all_nodes(self):
        edge12 = make_edge(self.entity1, self.entity2)
        edge23 = make_edge(self.entity2, self.entity3)
        neighbor_map = {
            self.entity1.global_id: ([self.entity2], [edge12]),
            self.entity2.global_id: ([self.entity3], [edge23]),
        }
        collector = DummyCollector(neighbor_map, Graph(nodes=[], edges=[]))

        result = collector.collect_since(self.entity1)

        self.assertTrue(result.contains_node(self.entity1))
        self.assertTrue(result.contains_node(self.entity2))
        self.assertTrue(result.contains_node(self.entity3))
        self.assertIn(edge12, result.edges)
        self.assertIn(edge23, result.edges)

    def test_collect_since_respects_max_iterations_stops_early(self):
        edge12 = make_edge(self.entity1, self.entity2)
        edge23 = make_edge(self.entity2, self.entity3)
        neighbor_map = {
            self.entity1.global_id: ([self.entity2], [edge12]),
            self.entity2.global_id: ([self.entity3], [edge23]),
        }
        collector = DummyCollector(neighbor_map, Graph(nodes=[], edges=[]))

        result = collector.collect_since(self.entity1, max_iterations=1)

        self.assertTrue(result.contains_node(self.entity1))
        self.assertTrue(result.contains_node(self.entity2))
        self.assertFalse(result.contains_node(self.entity3))
        self.assertIn(edge12, result.edges)
        self.assertNotIn(edge23, result.edges)

    def test_expand_graph_bfs_respects_ignore_sets_skips_nodes(self):
        edge12 = make_edge(self.entity1, self.entity2)
        neighbor_map = {self.entity1.global_id: ([self.entity2], [edge12])}
        collector = DummyCollector(neighbor_map, Graph(nodes=[], edges=[]))

        result = collector._expand_graph_bfs(
            Graph(nodes=[self.entity1], edges=[]),
            ignore_entity_ids={self.entity2.global_id},
            ignore_edge_ids={edge12.global_id},
        )

        self.assertTrue(result.contains_node(self.entity1))
        self.assertFalse(result.contains_node(self.entity2))
        self.assertEqual(len(result.edges), 0)

    def test_expand_graph_bfs_ignores_neighbor_errors_keeps_processed(self):
        collector = ExceptionCollector({}, Graph(nodes=[], edges=[]))

        result = collector._expand_graph_bfs(
            Graph(nodes=[self.entity1], edges=[]),
            ignore_entity_ids=None,
            ignore_edge_ids=None,
        )

        self.assertTrue(result.contains_node(self.entity1))
        self.assertEqual(len(result.nodes), 1)
        self.assertEqual(len(result.edges), 0)

    def test_collect_since_rejects_non_entity_type_error(self):
        collector = DummyCollector({}, Graph(nodes=[], edges=[]))
        with self.assertRaises(TypeError):
            collector.collect_since("not-entity")


class TestRegisteredCollectorRegistry(unittest.TestCase):
    def test_registered_collector_auto_registers_in_registry(self):
        class OneOffCollector(LocalCollector):
            def start(self):
                return None

            def stop(self):
                return None

            def clear(self):
                return None

            def _get_seed_graph(self) -> Graph:
                return Graph(nodes=[], edges=[])

            def get_neighbors_with_edges(self, entity: Entity):
                return [], []

        collectors = get_local_collectors()
        self.assertIn("OneOffCollector", collectors)
        self.assertIs(collectors["OneOffCollector"], OneOffCollector)


if __name__ == "__main__":
    unittest.main()
