"""
测试SocketCollector的功能是否正确

根据groundtruth的结果，从ground_truth_graph.nodes，看SocketCollector能否构建出相同的图
"""

import json
import os
import platform
from typing import Tuple
from unittest import TestCase, mock

import pandas as pd

from anansi.collector.local_collector.socket_collector import SocketCollector
from anansi.common.logging import get_logger
from anansi.common.timer import sync_wait_until
from anansi.common.worker_context import ProcessContextManager
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.edge.socket.socket_edge import DataFlowStats, SendToSocketEdge
from anansi.edge.socket.socket_monitor import get_socket_monitor
from anansi.edge.socket.socket_sniffer import SocketConnectionInfo
from anansi.edge.structual.belong import BelongEdge, OwnEdge
from anansi.entity.entity_base import Entity
from anansi.entity.node_entity import ProcessEntity, SocketEntity
from anansi.graph.graph import Graph
from tests.test_edge.test_socket.socket_traffic_generator import (
    SocketTrafficGeneratorConfig,
    start_generate_traffic,
)

LOGGER = get_logger(__name__)


def is_wsl() -> bool:
    """
    Checks if the current environment is Windows Subsystem for Linux (WSL).

    Returns:
        bool: True if running under WSL, False otherwise.
    """
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            # 读取文件内容并转换为小写，便于匹配
            version_info = f.read().lower()
            # WSL 1 包含 'microsoft'，WSL 2 包含 'microsoft' 并且内核版本更高或架构不同
            # 通常检查 'microsoft' 关键字就足够了
            return "microsoft" in version_info
    except FileNotFoundError:
        # 如果 /proc/version 不存在，则肯定不是 Linux 环境（自然也不是 WSL）
        return False
    except PermissionError:
        # 理论上不太可能遇到权限问题，但以防万一
        print("Warning: Could not read /proc/version due to permission error.")
        return False
    except Exception as e:
        # 捕获其他潜在异常
        print(
            f"Warning: An unexpected error occurred while checking /proc/version: {e}"
        )
        return False


class TestSocketCollector(TestCase):
    """
    Unit tests for `SocketCollector`.
    """

    @classmethod
    def setUpClass(cls):
        """Initialize test class."""
        LOGGER.info("Initializing test class `%s`", cls.__name__)

    def setUp(self):
        """Reset singleton state before each test."""
        self._generator_config = SocketTrafficGeneratorConfig()
        config = (
            GlobalConfigManager().get_config().collector_config.socket_collector_config
        )
        config.enable_filter = False

    def _load_ground_truth(self) -> Graph:
        """Load ground truth graph."""
        with open(self._generator_config.tgt_ground_truth_json_path, "r") as f:
            ground_truth = Graph(**json.load(f))
        # LOGGER.info("Loaded ground truth graph:\n%s", ground_truth.describe())
        return ground_truth

    def test_socket_collect_expand_from(self):
        """
        Test collecting socket topology since a given entity.

        Note:
        1. there could be other processes running on the system.
        2. Not all the processes in the ground truth graph is listener.
        """
        # 确保有数据
        collector = SocketCollector()

        try:
            LOGGER.debug("Starting Collector")
            collector.start()
            with ProcessContextManager(
                start_generate_traffic, config=self._generator_config, log_level="ERROR"
            ):
                # 等待几秒确保数据产生
                LOGGER.debug("Waiting for data to be generated")
                sync_wait_until(
                    lambda: collector.record_cnt_total > 3, timeout=10, check_interval=1
                )
                LOGGER.debug(
                    "Data generation complete: size=%s",
                    len(collector.sniffer.update_dataframe()),
                )

                ground_truth = self._load_ground_truth()
                LOGGER.info("Loaded ground truth graph: %s", ground_truth.describe())

                # 测试1： 从某个实体开始收集socket拓扑
                connected_subgraphs: list[Tuple[Entity, Graph]] = []
                with self.subTest(
                    "Test collecting socket topology since a given entity"
                ):
                    # 联通子图

                    for entity in ground_truth.nodes:
                        if not isinstance(entity, SocketEntity):
                            continue  # 只看socket节点
                        expanded_graph: Graph = collector.collect_since(entity)

                        # 如果节点属于某个联通子图，则两者应该完全相同
                        foundFlag = False
                        for _, subgraph in connected_subgraphs:
                            if entity in subgraph:
                                foundFlag = True
                                LOGGER.info(
                                    "Entity %s belongs to an existing connected subgraph, verifying equality.",
                                    entity.global_id,
                                )
                                self.assertEqual(
                                    len(subgraph.edges), len(expanded_graph.edges)
                                )
                                self.assertEqual(
                                    len(subgraph.nodes), len(expanded_graph.nodes)
                                )
                                if not is_wsl():
                                    self.assertEqual(subgraph, expanded_graph)
                        if not foundFlag:
                            LOGGER.info(
                                "Entity %s does not belong to any existing connected subgraph, adding new one.",
                                entity.global_id,
                            )
                            LOGGER.debug("subgraph:\n%s", expanded_graph.describe())
                            connected_subgraphs.append((entity, expanded_graph))
                with self.subTest("Test expanding socket topology from subgraphs"):
                    # 每个连通子图出一个点
                    subgraph_start_entities = [
                        entity for entity, _ in connected_subgraphs
                    ]
                    subgraph = Graph(nodes=subgraph_start_entities, edges=[])

                    expanded_graph = collector.expand_since_graph(subgraph)
                    # 理论上应该完全相等
                    LOGGER.info("Expanded graph:\n%s", expanded_graph.describe())
                    self.assertEqual(len(ground_truth.edges), len(expanded_graph.edges))
                    self.assertEqual(len(ground_truth.nodes), len(expanded_graph.nodes))
                    if not is_wsl():
                        self.assertEqual(len(ground_truth), len(expanded_graph))

                with self.subTest(
                    "Test expanding socket topology from a given subgraph"
                ):
                    socket_nodes = [
                        node
                        for node in ground_truth.nodes
                        if isinstance(node, SocketEntity)
                    ]
                    subgraph = Graph(nodes=socket_nodes, edges=[])

                    expanded_graph = collector.expand_since_graph(subgraph)
                    # 理论上应该完全相等
                    LOGGER.info("Expanded graph:\n%s", expanded_graph.describe())
                    self.assertEqual(len(ground_truth.edges), len(expanded_graph.edges))
                    self.assertEqual(len(ground_truth.nodes), len(expanded_graph.nodes))
                    if not is_wsl():
                        self.assertEqual(len(ground_truth), len(expanded_graph))
        except Exception as e:
            LOGGER.error("Test failed with exception: %s", e)
            raise e
        finally:
            collector.stop()
        LOGGER.info("Test passed")


if __name__ == "__main__":
    testcase = TestSocketCollector()
    testcase.setUpClass()
    testcase.setUp()
    testcase.test_socket_collect_expand_from()
    testcase.tearDown()
