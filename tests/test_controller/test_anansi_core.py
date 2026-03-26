import time
import unittest
from typing import Any, Tuple
from unittest.mock import Mock, patch

from anansi.collector.collect_set import CollectorSet
from anansi.collector.collector_base import Collector
from anansi.controller.anansi_core import AnansiCore
from anansi.edge.edge import Edge
from anansi.entity.entity_base import Entity
from anansi.entity.node_entity import ProcessEntity
from anansi.graph.graph import Graph
from anansi.subscriber.subscriber_base import Subscriber
from anansi.subscriber.subscriber_collection import SubscriberCollection


class MockCollector(Collector):
    """Mock collector for testing."""

    def __init__(self):
        self.started = False
        self.stopped = False
        self.cleared = False
        self._get_seed_graph_called = 0
        self._get_neighbors_called = 0
        self.mock_graph = Graph()

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def clear(self):
        self.cleared = True

    def _get_seed_graph(self) -> Graph:
        self._get_seed_graph_called += 1
        return self.mock_graph

    def get_neighbors_with_edges(
        self, entity: Entity
    ) -> Tuple[list[Entity], list[Edge]]:
        self._get_neighbors_called += 1
        return [], []


class MockSubscriber(Subscriber):
    """Mock subscriber for testing."""

    def __post_init__(self):
        self.received_graphs = []
        self.notify_called = False

    def _on_recv(self, target: Any):
        self.notify_called = True
        self.received_graphs.append(target)

    @property
    def expected_type(self) -> type[Any]:
        return Graph


class TestAnansiCore(unittest.TestCase):
    def setUp(self) -> None:
        AnansiCore.clear_singleton()
        # get_all_collectors returns dict[str, type], not dict[str, instance]
        self.mock_collectors_dict = {"mock_collector": MockCollector}
        self._config_patcher = patch(
            "anansi.controller.anansi_core.GlobalConfigManager"
        )
        self._mock_config_manager = self._config_patcher.start()
        mock_config = Mock()
        mock_config.collector_config = Mock(
            seed_graph_collectors=["MockCollector"],
            disabled_collectors=[],
            remote_slaves=[],
        )
        self._mock_config_manager.return_value.get_config.return_value = mock_config
        self._collect_set_patcher = patch(
            "anansi.collector.collect_set.GlobalConfigManager"
        )
        self._mock_collect_set_manager = self._collect_set_patcher.start()
        self._mock_collect_set_manager.return_value.get_config.return_value = (
            mock_config
        )

    def tearDown(self) -> None:
        # Clean up singleton instance after each test
        self._collect_set_patcher.stop()
        self._config_patcher.stop()
        AnansiCore.clear_singleton()

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_initialization(self, mock_get_local_collectors):
        """Test AnansiCore initialization."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()

        self.assertIsNotNone(core)
        subscriber_collection: SubscriberCollection = core.subscriber_collection()
        self.assertIsInstance(subscriber_collection, SubscriberCollection)
        collector_set: CollectorSet = core.get_collector_set()
        self.assertIsInstance(collector_set, CollectorSet)
        self.assertIn(MockCollector, [type(c) for c in collector_set.subcollectors])
        self.assertIsNotNone(core.subscriber_collection)
        self.assertEqual(core._running, 0)
        self.assertIsNone(core._thread)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_trigger_collect(self, mock_get_local_collectors):
        """Test trigger_collect calls collector and notifies subscribers."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()
        mock_subscriber = MockSubscriber()
        subscriber_collection: SubscriberCollection = core.subscriber_collection()
        subscriber_collection.register("test_sub", mock_subscriber)

        # Create a test graph
        test_graph = Graph(
            nodes=[ProcessEntity(pid=1, ppid=0, name="p1", cmdline="/bin/p1")],
            edges=[],
        )

        # Get the actual collector instance from CollectorSet
        # The CollectorSet creates instances from the collector classes
        collector_instance: MockCollector = core.get_collector_set().subcollectors[0]
        self.assertIsInstance(collector_instance, MockCollector)
        collector_instance.mock_graph = test_graph

        # Trigger collect
        core.trigger_collect()

        # Verify collector was called
        self.assertEqual(collector_instance._get_seed_graph_called, 1)
        self.assertGreater(collector_instance._get_neighbors_called, 0)

        # Verify subscriber was notified
        self.assertTrue(mock_subscriber.notify_called)
        self.assertEqual(len(mock_subscriber.received_graphs), 1)
        self.assertEqual(mock_subscriber.received_graphs[0], test_graph)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_trigger_clear(self, mock_get_local_collectors):
        """Test trigger_clear calls collector's clear method."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()
        # Get the actual collector instance from CollectorSet
        collector_instance: MockCollector = core.get_collector_set().subcollectors[0]
        self.assertIsInstance(collector_instance, MockCollector)
        core.trigger_clear()
        self.assertTrue(collector_instance.cleared)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_start_and_stop(self, mock_get_local_collectors):
        """Test start and stop methods."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()

        # Get the actual collector instance from CollectorSet
        collector_instance: MockCollector = core.get_collector_set().subcollectors[0]
        self.assertIsInstance(collector_instance, MockCollector)

        # Test start
        core.start()
        self.assertGreater(core._running, 0)
        self.assertIsNotNone(core._thread)
        self.assertTrue(core._thread.is_alive())
        self.assertTrue(collector_instance.started)

        # Give it a moment to ensure thread is running
        time.sleep(0.1)

        # Test stop
        core.stop()
        self.assertEqual(core._running, 0)

        # Wait for thread to finish
        time.sleep(0.3)

        if core._thread:
            self.assertFalse(core._thread.is_alive())
        self.assertTrue(collector_instance.stopped)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_start_already_running(self, mock_get_local_collectors):
        """Test starting when already running logs warning."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()
        core.start()

        with patch("anansi.controller.anansi_core.LOGGER") as mock_logger:
            core.start()
            mock_logger.warning.assert_called_once()

        core.stop()

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_stop_not_running(self, mock_get_local_collectors):
        """Test stopping when not running logs warning."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()

        with patch("anansi.controller.anansi_core.LOGGER") as mock_logger:
            core.stop()
            mock_logger.warning.assert_called_once()

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_get_last_graph(self, mock_get_local_collectors):
        """Test get_last_graph returns the latest graph."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()

        # Initially should return empty graph
        graph = core.get_last_graph()
        self.assertIsInstance(graph, Graph)

        # After triggering collect, should return the collected graph
        test_graph = Graph()

        # Get the actual collector instance from CollectorSet
        collector_instance: MockCollector = core.get_collector_set().subcollectors[0]
        self.assertIsInstance(collector_instance, MockCollector)
        collector_instance.mock_graph = test_graph

        core.trigger_collect()

        last_graph = core.get_last_graph()
        self.assertEqual(last_graph, test_graph)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_multiple_subscribers(self, mock_get_local_collectors):
        """Test multiple subscribers all get notified."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()

        # Register multiple subscribers
        sub1 = MockSubscriber("sub1")
        sub2 = MockSubscriber("sub2")
        sub3 = MockSubscriber("sub3")

        subscriber_collection: SubscriberCollection = core.subscriber_collection()
        subscriber_collection.register("sub1", sub1)
        subscriber_collection.register("sub2", sub2)
        subscriber_collection.register("sub3", sub3)

        # Trigger collect
        test_graph = Graph()

        # Get the actual collector instance from CollectorSet
        collector_instance: MockCollector = core.get_collector_set().subcollectors[0]
        self.assertIsInstance(collector_instance, MockCollector)
        collector_instance.mock_graph = test_graph

        core.trigger_collect()

        # Verify all subscribers were notified
        self.assertTrue(sub1.notify_called)
        self.assertTrue(sub2.notify_called)
        self.assertTrue(sub3.notify_called)

        self.assertEqual(len(sub1.received_graphs), 1)
        self.assertEqual(len(sub2.received_graphs), 1)
        self.assertEqual(len(sub3.received_graphs), 1)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_singleton_pattern(self, mock_get_local_collectors):
        """Test AnansiCore follows singleton pattern."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core1 = AnansiCore()
        core2 = AnansiCore()

        self.assertIs(core1, core2)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_loop_triggers_collect_periodically(self, mock_get_local_collectors):
        """Test that the loop triggers collection periodically."""
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()
        mock_subscriber = MockSubscriber()
        # Set a short interval for the new subscriber; collection uses min(intervals)
        mock_subscriber.expected_update_interval = 0.1
        subscriber_collection: SubscriberCollection = core.subscriber_collection()
        subscriber_collection.register("test_sub", mock_subscriber)

        # Start the core
        core.start()

        # Wait for multiple collection cycles (fast interval, loop sleeps 0.5s)
        time.sleep(2.0)

        # Stop the core
        core.stop()

        # Should have been called multiple times with short interval
        self.assertGreaterEqual(len(mock_subscriber.received_graphs), 2)

    @patch("anansi.controller.anansi_core.get_local_collectors")
    def test_multiple_running_instance(self, mock_get_local_collectors):
        mock_get_local_collectors.return_value = self.mock_collectors_dict

        core = AnansiCore()
        collector: MockCollector = core.get_collector_set().subcollectors[0]
        self.assertIsInstance(collector, MockCollector)

        core.start()
        core.start()
        time.sleep(1.0)
        core.stop()
        self.assertEqual(core._running, 1)
        self.assertFalse(collector.stopped)
        core.stop()
        self.assertEqual(core._running, 0)
        self.assertTrue(collector.stopped)


if __name__ == "__main__":
    unittest.main()
