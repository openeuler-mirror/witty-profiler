"""
CollectorSet单元测试
测试CollectorSet类对多个子收集器的管理和协调功能
"""

import unittest
from unittest.mock import Mock, patch

from anansi.collector.collect_set import CollectorSet
from anansi.collector.local_collector import LocalCollector
from anansi.edge.edge import DirectedEdge
from anansi.entity.node_entity import ProcessEntity
from anansi.graph.graph import Graph


# ============= Mock辅助类 =============
class MockCollector(LocalCollector):
    """模拟收集器，用于测试CollectorSet"""

    def __init__(self, seed_graph=None, neighbors=None, name="MockCollector"):
        # 初始化模拟收集器
        super().__init__()  # 调用父类初始化
        self.name = name
        self.seed_graph = seed_graph or Graph(nodes=[], edges=[])
        self.neighbors = neighbors or ([], [])
        self.started = False
        self.stopped = False
        self.cleared = False
        self.start_count = 0
        self.stop_count = 0
        self.clear_count = 0

    def start(self):
        """启动模拟收集器"""
        self.started = True
        self.start_count += 1

    def stop(self):
        """停止模拟收集器"""
        self.stopped = True
        self.stop_count += 1

    def clear(self):
        """清空模拟收集器状态"""
        self.cleared = True
        self.clear_count += 1

    def _get_seed_graph(self) -> Graph:
        """获取种子图"""
        return self.seed_graph

    def get_neighbors_with_edges(self, entity):
        """获取邻居实体和边"""
        return self.neighbors


class TestCollectorSetInit(unittest.TestCase):
    """测试CollectorSet的初始化"""

    def test_init_with_single_collector(self):
        """测试用单个收集器初始化CollectorSet"""
        mock_collector = MockCollector(name="Single")
        collector_set = CollectorSet([mock_collector])

        self.assertEqual(len(collector_set.subcollectors), 1)
        self.assertIn(mock_collector, collector_set.subcollectors)

    def test_init_with_multiple_collectors(self):
        """测试用多个收集器初始化CollectorSet"""
        collectors = [
            MockCollector(name="Collector1"),
            MockCollector(name="Collector2"),
            MockCollector(name="Collector3"),
        ]
        collector_set = CollectorSet(collectors)

        self.assertEqual(len(collector_set.subcollectors), 3)
        for collector in collectors:
            self.assertIn(collector, collector_set.subcollectors)

    def test_init_with_empty_list(self):
        """测试用空列表初始化CollectorSet"""
        collector_set = CollectorSet([])

        self.assertEqual(len(collector_set.subcollectors), 0)
        self.assertIsInstance(collector_set.subcollectors, list)


class TestCollectorSetLifecycle(unittest.TestCase):
    """测试CollectorSet的生命周期管理方法（start/stop/clear）"""

    def setUp(self):
        """测试前的准备工作"""
        self.collector1 = MockCollector(name="Collector1")
        self.collector2 = MockCollector(name="Collector2")
        self.collector_set = CollectorSet([self.collector1, self.collector2])

    def test_start_calls_all_subcollectors(self):
        """测试start方法调用所有子收集器的start方法"""
        self.collector_set.start()

        # 验证每个子收集器的start方法都被调用
        self.assertTrue(self.collector1.started)
        self.assertTrue(self.collector2.started)
        self.assertEqual(self.collector1.start_count, 1)
        self.assertEqual(self.collector2.start_count, 1)

    def test_stop_calls_all_subcollectors(self):
        """测试stop方法调用所有子收集器的stop方法"""
        # CollectorSet.stop 仅在已启动时才会向子收集器传播
        self.collector_set.start()
        self.collector_set.stop()

        # 验证每个子收集器的stop方法都被调用
        self.assertTrue(self.collector1.stopped)
        self.assertTrue(self.collector2.stopped)
        self.assertEqual(self.collector1.stop_count, 1)
        self.assertEqual(self.collector2.stop_count, 1)

    def test_clear_calls_all_subcollectors(self):
        """测试clear方法调用所有子收集器的clear方法"""
        self.collector_set.clear()

        # 验证每个子收集器的clear方法都被调用
        self.assertTrue(self.collector1.cleared)
        self.assertTrue(self.collector2.cleared)
        self.assertEqual(self.collector1.clear_count, 1)
        self.assertEqual(self.collector2.clear_count, 1)

    def test_multiple_start_calls(self):
        """测试多次调用start方法"""
        self.collector_set.start()
        self.collector_set.start()
        self.collector_set.start()

        # CollectorSet.start 现为幂等操作：仅第一次调用触发子收集器
        self.assertEqual(self.collector1.start_count, 1)
        self.assertEqual(self.collector2.start_count, 1)

    def test_lifecycle_sequence(self):
        """测试完整的生命周期序列：start -> clear -> stop"""
        # 启动
        self.collector_set.start()
        self.assertTrue(self.collector1.started)
        self.assertTrue(self.collector2.started)

        # 清空
        self.collector_set.clear()
        self.assertTrue(self.collector1.cleared)
        self.assertTrue(self.collector2.cleared)

        # 停止
        self.collector_set.stop()
        self.assertTrue(self.collector1.stopped)
        self.assertTrue(self.collector2.stopped)

    def test_start_with_empty_subcollectors(self):
        """测试空子收集器列表时调用start不抛出异常"""
        empty_set = CollectorSet([])
        empty_set.start()  # 不应该抛出异常

    def test_stop_with_empty_subcollectors(self):
        """测试空子收集器列表时调用stop不抛出异常"""
        empty_set = CollectorSet([])
        empty_set.stop()  # 不应该抛出异常

    def test_clear_with_empty_subcollectors(self):
        """测试空子收集器列表时调用clear不抛出异常"""
        empty_set = CollectorSet([])
        empty_set.clear()  # 不应该抛出异常


class TestCollectorSetGraphOperations(unittest.TestCase):
    """测试CollectorSet的图操作方法（_get_seed_graph和get_neighbors_with_edges）"""

    def setUp(self):
        """准备测试数据"""
        # 创建不同的实体
        self.entity1 = ProcessEntity(pid=1, ppid=0, name="p1", cmdline="/bin/p1")
        self.entity2 = ProcessEntity(pid=2, ppid=0, name="p2", cmdline="/bin/p2")
        self.entity3 = ProcessEntity(pid=3, ppid=0, name="p3", cmdline="/bin/p3")

        # 创建边
        self.edge1 = DirectedEdge(source_node=self.entity1, target_node=self.entity2)
        self.edge2 = DirectedEdge(source_node=self.entity2, target_node=self.entity3)

        self._config_patcher = patch("anansi.collector.collect_set.GlobalConfigManager")
        self._mock_config_manager = self._config_patcher.start()
        mock_config = Mock()
        mock_config.collector_config = Mock(seed_graph_collectors=["MockCollector"])
        self._mock_config_manager.return_value.get_config.return_value = mock_config

    def tearDown(self):
        self._config_patcher.stop()

    def test_get_seed_graph_merges_all_subcollectors(self):
        """测试_get_seed_graph合并所有子收集器的种子图"""
        # 创建两个收集器，各有不同的种子图
        collector1 = MockCollector(
            seed_graph=Graph(nodes=[self.entity1], edges=[self.edge1]),
            name="Collector1",
        )
        collector2 = MockCollector(
            seed_graph=Graph(nodes=[self.entity2], edges=[self.edge2]),
            name="Collector2",
        )
        collector_set = CollectorSet([collector1, collector2])

        # 获取合并后的种子图
        merged_graph = collector_set._get_seed_graph()

        # 验证合并后的图包含所有实体和边
        self.assertIn(self.entity1, merged_graph.nodes)
        self.assertIn(self.entity2, merged_graph.nodes)
        self.assertIn(self.edge1, merged_graph.edges)
        self.assertIn(self.edge2, merged_graph.edges)

    def test_get_seed_graph_with_overlapping_entities(self):
        """测试_get_seed_graph处理重复实体的情况"""
        # 两个收集器返回相同的实体
        collector1 = MockCollector(
            seed_graph=Graph(nodes=[self.entity1], edges=[]), name="Collector1"
        )
        collector2 = MockCollector(
            seed_graph=Graph(nodes=[self.entity1], edges=[]), name="Collector2"
        )
        collector_set = CollectorSet([collector1, collector2])

        merged_graph = collector_set._get_seed_graph()

        # 验证重复实体只出现一次（Graph.merge_graphs应处理去重）
        entity_ids = [node.global_id for node in merged_graph.nodes]
        self.assertEqual(entity_ids.count(self.entity1.global_id), 1)

    def test_get_seed_graph_with_empty_subcollectors(self):
        """测试空子收集器列表时_get_seed_graph返回空图"""
        collector_set = CollectorSet([])
        seed_graph = collector_set._get_seed_graph()

        self.assertEqual(len(seed_graph.nodes), 0)
        self.assertEqual(len(seed_graph.edges), 0)

    def test_get_neighbors_with_edges_aggregates_results(self):
        """测试get_neighbors_with_edges聚合所有子收集器的结果"""
        # 第一个收集器返回entity2和edge1
        collector1 = MockCollector(
            neighbors=([self.entity2], [self.edge1]), name="Collector1"
        )
        # 第二个收集器返回entity3和edge2
        collector2 = MockCollector(
            neighbors=([self.entity3], [self.edge2]), name="Collector2"
        )
        collector_set = CollectorSet([collector1, collector2])

        # 查询entity1的邻居
        neighbors, edges = collector_set.get_neighbors_with_edges(self.entity1)

        # 验证返回所有邻居和边
        self.assertIn(self.entity2, neighbors)
        self.assertIn(self.entity3, neighbors)
        self.assertIn(self.edge1, edges)
        self.assertIn(self.edge2, edges)
        self.assertEqual(len(neighbors), 2)
        self.assertEqual(len(edges), 2)

    def test_get_neighbors_with_edges_handles_empty_results(self):
        """测试get_neighbors_with_edges处理子收集器返回空结果"""
        collector1 = MockCollector(neighbors=([], []), name="Collector1")
        collector2 = MockCollector(neighbors=([], []), name="Collector2")
        collector_set = CollectorSet([collector1, collector2])

        neighbors, edges = collector_set.get_neighbors_with_edges(self.entity1)

        self.assertEqual(len(neighbors), 0)
        self.assertEqual(len(edges), 0)

    def test_get_neighbors_with_edges_with_partial_results(self):
        """测试get_neighbors_with_edges处理部分子收集器返回空结果"""
        # 第一个收集器返回结果
        collector1 = MockCollector(
            neighbors=([self.entity2], [self.edge1]), name="Collector1"
        )
        # 第二个收集器返回空结果
        collector2 = MockCollector(neighbors=([], []), name="Collector2")
        collector_set = CollectorSet([collector1, collector2])

        neighbors, edges = collector_set.get_neighbors_with_edges(self.entity1)

        # 验证只包含第一个收集器的结果
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(len(edges), 1)
        self.assertIn(self.entity2, neighbors)
        self.assertIn(self.edge1, edges)

    def test_get_neighbors_with_edges_with_duplicate_results(self):
        """测试get_neighbors_with_edges处理重复结果（多个收集器返回相同实体/边）"""
        # 两个收集器返回相同的邻居和边
        collector1 = MockCollector(
            neighbors=([self.entity2], [self.edge1]), name="Collector1"
        )
        collector2 = MockCollector(
            neighbors=([self.entity2], [self.edge1]), name="Collector2"
        )
        collector_set = CollectorSet([collector1, collector2])

        neighbors, edges = collector_set.get_neighbors_with_edges(self.entity1)

        # 注意：CollectorSet只是简单extend，不做去重
        # 所以会包含重复项（这是预期行为）
        self.assertEqual(len(neighbors), 2)
        self.assertEqual(len(edges), 2)

    def test_get_neighbors_with_edges_with_empty_subcollectors(self):
        """测试空子收集器列表时get_neighbors_with_edges返回空列表"""
        collector_set = CollectorSet([])
        neighbors, edges = collector_set.get_neighbors_with_edges(self.entity1)

        self.assertEqual(len(neighbors), 0)
        self.assertEqual(len(edges), 0)


class TestCollectorSetEdgeCases(unittest.TestCase):
    """测试CollectorSet的边界情况和异常场景"""

    def test_subcollector_raises_exception_in_start(self):
        """测试子收集器在start中抛出异常的情况"""

        class ExceptionCollector(MockCollector):
            def start(self):
                raise RuntimeError("Start failed")

        collector1 = MockCollector(name="Normal")
        collector2 = ExceptionCollector(name="Exception")
        collector_set = CollectorSet([collector1, collector2])

        # start应该传播异常
        with self.assertRaises(RuntimeError):
            collector_set.start()

    def test_subcollector_raises_exception_in_get_seed_graph(self):
        """测试子收集器在_get_seed_graph中抛出异常的情况"""

        class ExceptionCollector(MockCollector):
            def _get_seed_graph(self):
                raise ValueError("Get seed graph failed")

        collector1 = MockCollector(
            seed_graph=Graph(
                nodes=[ProcessEntity(pid=1, ppid=0, name="p1", cmdline="/bin/p1")],
                edges=[],
            ),
            name="Normal",
        )
        collector2 = ExceptionCollector(name="Exception")
        collector_set = CollectorSet([collector1, collector2])

        with patch("anansi.collector.collect_set.GlobalConfigManager") as mock_mgr:
            mock_config = Mock()
            mock_config.collector_config = Mock(
                seed_graph_collectors=["MockCollector", "ExceptionCollector"]
            )
            mock_mgr.return_value.get_config.return_value = mock_config

            seed_graph = collector_set._get_seed_graph()
            self.assertEqual(len(seed_graph.nodes), 1)

    def test_with_single_collector(self):
        """测试只有一个子收集器的CollectorSet"""
        entity = ProcessEntity(pid=10, ppid=0, name="p10", cmdline="/bin/p10")

        collector = MockCollector(
            seed_graph=Graph(nodes=[entity], edges=[]),
            neighbors=([entity], []),
            name="Single",
        )
        collector_set = CollectorSet([collector])

        # 测试所有方法都正常工作
        collector_set.start()
        self.assertTrue(collector.started)

        with patch("anansi.collector.collect_set.GlobalConfigManager") as mock_mgr:
            mock_config = Mock()
            mock_config.collector_config = Mock(seed_graph_collectors=["MockCollector"])
            mock_mgr.return_value.get_config.return_value = mock_config

            seed_graph = collector_set._get_seed_graph()
            self.assertEqual(len(seed_graph.nodes), 1)

        neighbors, edges = collector_set.get_neighbors_with_edges(entity)
        self.assertEqual(len(neighbors), 1)

        collector_set.stop()
        self.assertTrue(collector.stopped)

    def test_with_many_subcollectors(self):
        """测试有大量子收集器的CollectorSet"""
        collectors = [MockCollector(name=f"Collector{i}") for i in range(10)]
        collector_set = CollectorSet(collectors)

        collector_set.start()
        for collector in collectors:
            self.assertTrue(collector.started)

        collector_set.stop()
        for collector in collectors:
            self.assertTrue(collector.stopped)


class TestCollectorSetIntegration(unittest.TestCase):
    """CollectorSet的集成测试"""

    def test_full_workflow_with_multiple_collectors(self):
        """测试完整工作流程：初始化 -> 启动 -> 获取图 -> 获取邻居 -> 清空 -> 停止"""
        # 准备测试数据
        entity1 = ProcessEntity(pid=101, ppid=0, name="p101", cmdline="/bin/p101")
        entity2 = ProcessEntity(pid=102, ppid=0, name="p102", cmdline="/bin/p102")
        edge = DirectedEdge(source_node=entity1, target_node=entity2)

        # 创建两个有实际数据的收集器
        collector1 = MockCollector(
            seed_graph=Graph(nodes=[entity1], edges=[]),
            neighbors=([entity2], [edge]),
            name="Collector1",
        )
        collector2 = MockCollector(
            seed_graph=Graph(nodes=[entity2], edges=[]),
            neighbors=([], []),
            name="Collector2",
        )

        # 创建CollectorSet
        collector_set = CollectorSet([collector1, collector2])

        # 1. 启动
        collector_set.start()
        self.assertTrue(collector1.started)
        self.assertTrue(collector2.started)

        # 2. 获取种子图
        with patch("anansi.collector.collect_set.GlobalConfigManager") as mock_mgr:
            mock_config = Mock()
            mock_config.collector_config = Mock(seed_graph_collectors=["MockCollector"])
            mock_mgr.return_value.get_config.return_value = mock_config

            seed_graph = collector_set._get_seed_graph()
            self.assertGreaterEqual(len(seed_graph.nodes), 1)

        # 3. 获取邻居
        neighbors, edges = collector_set.get_neighbors_with_edges(entity1)
        self.assertGreaterEqual(len(neighbors), 1)

        # 4. 清空
        collector_set.clear()
        self.assertTrue(collector1.cleared)
        self.assertTrue(collector2.cleared)

        # 5. 停止
        collector_set.stop()
        self.assertTrue(collector1.stopped)
        self.assertTrue(collector2.stopped)


if __name__ == "__main__":
    # 运行单元测试
    unittest.main()
