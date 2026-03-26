import json
import logging
import os
import random
import time
import unittest
from unittest import TestCase

from witty_profiler.collector.local_collector.shm_collector import SharedMemoryCollector
from witty_profiler.common.id_manager import GlobalIDManager
from witty_profiler.common.logging import get_logger
from witty_profiler.common.worker_context import ProcessContextManager
from witty_profiler.edge.structual.belong import AccessEdge
from witty_profiler.entity.node_entity import ProcessEntity, SharedMemoryEntity
from witty_profiler.graph.graph import Graph
from tests.test_edge.test_shmm.shmm_generator import (
    shmm_graph_start,
    wait_for_condition,
)

LOGGER = get_logger(__name__)

GROUND_TRUTH_GRAPH_FILE = os.path.join(
    os.path.dirname(__file__), "local", "ground_truth.json"
)


def load_ground_truth() -> Graph:

    with open(GROUND_TRUTH_GRAPH_FILE, "r") as f:
        ground_truth = Graph(**json.load(f))
    # LOGGER.info("Loaded ground truth graph:\n%s", ground_truth.describe())
    return ground_truth


def generate_shmm(num_processes=2, connection_probability=1.0):
    LOGGER.info(
        "Generating shared memory graph with %d processes and %f connection probability",
        num_processes,
        connection_probability,
    )
    if os.path.exists(GROUND_TRUTH_GRAPH_FILE):
        os.remove(GROUND_TRUTH_GRAPH_FILE)
    logger = get_logger(name=None)
    logger.setLevel(logging.ERROR)
    shmm_graph_start(
        num_processes=num_processes,
        connection_probability=connection_probability,
        graph_file_path=GROUND_TRUTH_GRAPH_FILE,
        rounds=0,  # forever
        interval=1.0,
    )


class TestSharedMemoryCollector(TestCase):
    def setUp(self) -> None:
        if os.path.exists(GROUND_TRUTH_GRAPH_FILE):
            os.remove(GROUND_TRUTH_GRAPH_FILE)
        LOGGER.info(
            "Set up for TestSharedMemorySniffer, removed existing ground truth file."
        )

    def test_shared_memory_collect(self):
        with ProcessContextManager(
            generate_shmm, num_processes=5, connection_probability=1.0
        ) as proc:
            wait_for_condition(
                lambda: os.path.exists(GROUND_TRUTH_GRAPH_FILE),
                timeout=10,
                step=0.5,
            )
            time.sleep(0.5)  # 先跑一会创建拓扑
            graph: Graph = load_ground_truth()
            LOGGER.info("Shared memory graph generated: \n%s", graph.describe())
            collector = SharedMemoryCollector()
            new_graph: Graph = None
            for node in graph.nodes:
                # 从任意一个节点出发可以得到整张图
                LOGGER.info("Collecting graph from node %s", node.global_id)
                new_graph = collector.collect_since(node)
                if graph != new_graph:
                    LOGGER.info("New graph: \n%s", new_graph.describe())
                self.assertEqual(
                    new_graph,
                    graph,
                    (
                        f"Collected graph from node {node.global_id} "
                        f"does not match "
                        f"ground truth graph",
                    ),
                )
        LOGGER.info("Test completed.")

    def test_shared_memory_expand(self):
        """从子图开始，扩展图"""
        with ProcessContextManager(generate_shmm) as proc:
            time.sleep(0.5)  # 先跑一会创建拓扑
            wait_for_condition(
                lambda: os.path.exists(GROUND_TRUTH_GRAPH_FILE),
                timeout=10,
                step=0.5,
            )
            LOGGER.info(
                "Shared memory graph generated: \n%s",
                load_ground_truth().describe(),
            )
            collector = SharedMemoryCollector()
            graph: Graph = load_ground_truth()
            subgraph = Graph(
                nodes=[],
                edges=random.sample(graph.edges, k=random.randint(1, len(graph.edges))),
            )
            new_graph = collector.expand_since_graph(subgraph)
            self.assertEqual(
                new_graph,
                graph,
                (
                    f"Collected graph from subgraph "
                    f"does not match "
                    f"ground truth graph",
                ),
            )
        LOGGER.info("Collected graph from subgraph matches ground truth graph")

    def test_shared_memory_expand_ex(self):
        """从空的始点开始，扩展图"""
        with ProcessContextManager(
            generate_shmm, num_processes=5, connection_probability=0.5
        ) as proc:
            time.sleep(0.5)  # 先跑一会创建拓扑
            wait_for_condition(
                lambda: os.path.exists(GROUND_TRUTH_GRAPH_FILE),
                timeout=10,
                step=0.5,
            )
            graph: Graph = load_ground_truth()
            LOGGER.info(
                "Shared memory graph generated: \n%s",
                graph.describe(),
            )
            collector = SharedMemoryCollector()

            subgraph = Graph(
                nodes=graph.nodes,
                edges=[],
            )
            new_graph = collector.expand_since_graph(subgraph)
            self.assertEqual(
                new_graph,
                graph,
                (
                    f"Collected graph from subgraph "
                    f"does not match "
                    f"ground truth graph",
                ),
            )
            LOGGER.info(
                "Collected graph from empty-edge subgraph matches ground truth graph: \n%s",
                new_graph.describe(),
            )

    def test_shared_memory_collect_whole_graph(self):
        with ProcessContextManager(
            generate_shmm, num_processes=6, connection_probability=0.5
        ) as proc:
            time.sleep(0.5)  # 先跑一会创建拓扑
            wait_for_condition(
                lambda: os.path.exists(GROUND_TRUTH_GRAPH_FILE),
                timeout=10,
                step=0.5,
            )
            graph: Graph = load_ground_truth()
            LOGGER.info(
                "Shared memory graph generated: \n%s",
                graph.describe(),
            )

            collector = SharedMemoryCollector()
            collected_graph: Graph = collector.collect_whole_graph()
            LOGGER.debug(
                "Collected shared memory graph: \n%s", collected_graph.describe()
            )

            # 构造的case里，有的process没有shared memory，所以这里不能用equal
            self.assertLessEqual(collected_graph, graph)

            connected_nodes = {
                node.global_id for edge in graph.edges for node in edge.nodes
            }
            manager: GlobalIDManager = GlobalIDManager.get_instance()
            connected_nodes = [
                manager.lookup_by_global_id(node_id) for node_id in connected_nodes
            ]
            connected_graph = Graph(nodes=connected_nodes, edges=graph.edges)
            self.assertEqual(collected_graph, connected_graph)
            LOGGER.info(
                "Collected shared memory graph matches ground truth graph: \n%s",
                collected_graph.describe(),
            )

    def test_shared_memory_collector_invalid_input(self):
        collector = SharedMemoryCollector()
        with self.assertRaises((TypeError)) as cm:
            collector.collect_since(None)  # Invalid Input
        self.assertIsInstance(cm.exception, TypeError)
        self.assertIn(
            "Input must be an Entity instance",
            str(cm.exception),
        )


if __name__ == "__main__":
    """
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSharedMemoryCollector)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    #"""
    test_case = TestSharedMemoryCollector()
    test_case.setUp()
    test_case.test_shared_memory_collect_whole_graph()
