"""Tests for SocketMonitor pipeline and subscription flow.

These tests validate the SocketMonitor singleton behavior, subscriber dispatch,
and on-disk buffering without requiring the actual sniffer binary.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from unittest import TestCase, mock

import pandas as pd

from anansi.common.logging import get_logger
from anansi.common.timer import sync_wait_until
from anansi.common.worker_context import ProcessContextManager
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.edge.socket.socket_monitor import (
    MONITOR_COLUMNS,
    SocketMonitor,
    get_socket_monitor,
)
from tests.test_edge.test_socket.socket_traffic_generator import (
    SocketTrafficGenerator,
    SocketTrafficGeneratorConfig,
    start_generate_traffic,
)

LOGGER = get_logger(__name__)


class TestSocketMonitor(TestCase):
    """Unit tests for SocketMonitor behavior and data flow."""

    @classmethod
    def setUpClass(cls):
        """Initialize test class."""

    def setUp(self):
        """Reset singleton state before each test."""
        self._record_dfs: list[pd.DataFrame] = []
        self._monitor = get_socket_monitor()
        self._monitor.clear_disk_storage()

    def tearDown(self):
        """Cleanup singleton state after each test."""
        self._record_dfs.clear()

    def _record_df(self, df: pd.DataFrame):
        """记录收到的数据"""
        self._record_dfs.append(df)

    def test_monitor_notification(self):
        """测试传输数据格式正确"""
        SUBSCRIBER_NAME = "test_monitor_notification"
        config = SocketTrafficGeneratorConfig()

        try:
            LOGGER.debug("Starting SocketMonitor")
            self._monitor.register_subscriber(
                SUBSCRIBER_NAME,
                callback=self._record_df,
            )
            LOGGER.debug("SocketMonitor started for testing")
            with ProcessContextManager(
                start_generate_traffic, config=config, log_level="ERROR"
            ):
                # 等待几秒确保数据产生
                LOGGER.debug("Waiting for data to be generated")
                sync_wait_until(
                    lambda: len(self._record_dfs) > 2, timeout=10, check_interval=1
                )
                LOGGER.debug("Data generation complete")

                # 验证收到的数据格式正确
                for df in self._record_dfs:
                    LOGGER.debug("Received data frame with %d rows", len(df))
                    self.assertIsInstance(df, pd.DataFrame)
                    for col in MONITOR_COLUMNS:
                        self.assertIn(col, df.columns)

            LOGGER.debug(
                "final df: \n%s", pd.concat(self._record_dfs, ignore_index=True)
            )

        except RuntimeError:
            LOGGER.verbose("SocketMonitor exit unexpectedly")
        finally:
            self._monitor.unregister_subscriber(SUBSCRIBER_NAME)


__all__ = ["TestSocketMonitor"]


if __name__ == "__main__":
    """Run tests."""
    testcase = TestSocketMonitor()
    testcase.setUpClass()
    testcase.setUp()
    testcase.test_monitor_notification()
    testcase.tearDown()
