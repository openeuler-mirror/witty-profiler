"""
测试SocketSniffer的功能是否正确

根据groundtruth的结果，判断收到的数据groundtruth中发送的数据，是否都包括在采集到的数据中
注意：
    由于系统中可能的socket链接可能是测试graph的一部分，而不是完全匹配
    因此只需要判断采集到的数据是否包含groundtruth中发送的数据即可


"""

import json
import os
import tempfile
import time
from dataclasses import dataclass
from unittest import TestCase, mock

import pandas as pd

from witty_profiler.common.logging import get_logger
from witty_profiler.common.timer import sync_wait_until
from witty_profiler.common.worker_context import ProcessContextManager
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.edge.socket.socket_edge import DataFlowStats, SendToSocketEdge
from witty_profiler.edge.socket.socket_monitor import (
    MONITOR_COLUMNS,
    SocketMonitor,
    get_socket_monitor,
)
from witty_profiler.edge.socket.socket_sniffer import (
    SocketConnectionInfo,
    SocketSniffer,
    get_socket_sniffer,
)
from witty_profiler.entity.node_entity import ProcessEntity, SocketEntity
from witty_profiler.graph.graph import Graph
from tests.test_edge.test_socket.socket_traffic_generator import (
    SocketTrafficGeneratorConfig,
    start_generate_traffic,
)

LOGGER = get_logger(__name__)


class TestSocketSniffer(TestCase):
    """Unit tests for SocketSniffer behavior and data flow."""

    @classmethod
    def setUpClass(cls):
        """Initialize test class."""

    def setUp(self):
        """Reset singleton state before each test."""
        self._generator_config = SocketTrafficGeneratorConfig()

    def _load_ground_truth(self) -> Graph:
        """Load ground truth graph."""

        with open(self._generator_config.tgt_ground_truth_json_path, "r") as f:
            ground_truth = Graph(**json.load(f))
        # LOGGER.info("Loaded ground truth graph:\n%s", ground_truth.describe())
        return ground_truth

    def test_sniffer_edges_correctness(self):
        # 确保有数据
        SUBSCRIBER_NAME = "test_sniffer_edges_correctness"

        sniffer: SocketSniffer = get_socket_sniffer()
        try:
            sniffer.start()
            with ProcessContextManager(
                start_generate_traffic, config=self._generator_config, log_level="ERROR"
            ):
                # 等待几秒确保数据产生
                LOGGER.debug("Waiting for data to be generated")
                sync_wait_until(
                    lambda: sniffer.record_cnt_total > 2, timeout=10, check_interval=1
                )
                LOGGER.debug(
                    "Data generation complete:\n%s", sniffer.update_dataframe()
                )

                # 读取ground truth
                ground_truth = self._load_ground_truth()
                # 检查
                for node in ground_truth.nodes:
                    if not isinstance(node, SocketEntity):
                        continue
                    # 对每个ListenSocket检查发往该Socket的进程数是否一致
                    LOGGER.debug("Checking node: %s", node.global_id)
                    # Ground Truth中发往该Socket的进程
                    expected_sender_pid = set()
                    for edge in ground_truth.edges:
                        if not isinstance(edge, SendToSocketEdge):
                            continue
                        if edge.target_node == node:
                            expected_sender_pid.add(edge.source_node.pid)
                    results: list[SocketConnectionInfo] = sniffer.query_send_to_socket(
                        node.socket_addr, node.socket_port
                    )
                    sender_pid = set()
                    for info in results:
                        sender_pid.add(info.local_pid)

                    self.assertEqual(
                        len(expected_sender_pid),
                        len(sender_pid),
                        (
                            f"Recv at {node.socket_addr}:{node.socket_port} "
                            f"processes size mismatch. GT:\n{ground_truth.describe()}"
                        ),
                    )
            LOGGER.info("Test completed successfully")
        except RuntimeError as e:
            LOGGER.error("Error occurred during test: %s", e)
            raise
        finally:
            LOGGER.info("Stopping socket sniffer")
            sniffer.stop()


if __name__ == "__main__":
    """Run tests."""
    testcase = TestSocketSniffer()
    testcase.setUpClass()
    testcase.setUp()
    testcase.test_sniffer_edges_correctness()
    testcase.tearDown()
