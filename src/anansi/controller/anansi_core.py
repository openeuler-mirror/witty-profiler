"""Core orchestrator for topology collection and subscriber notification.

Provides AnansiCore, a thread-safe singleton that manages the lifecycle
of all collectors and subscribers. It coordinates periodic graph collection
from multiple data sources (socket sniffers, IPC, shared memory) and
notifies subscribers of topology updates.

Key Components:
    - AnansiCore: Main singleton controller with start/stop/trigger methods
    - Uses CollectorSet to manage multiple collectors (socket, IPC, shared memory)
    - Maintains NaiveMemoryStorageGraphSubscriber for in-memory graph storage
    - Runs a background thread that periodically triggers collection based on
        subscriber update intervals

Lifecycle:
    1. AnansiCore.get_instance() - Get singleton instance
    2. start() - Initialize collectors, start background collection loop
    3. trigger_collect() - Manual trigger for topology collection
    4. get_last_graph() - Retrieve latest collected topology
    5. stop() - Cleanup and shut down

Thread Safety:
    All lifecycle methods protected by RLock. Supports nested start/stop calls
    via reference counting (_running counter).

Notes:
    - Background loop uses sync_wait_until() with configurable timeout
    - stop_event signals graceful shutdown; join waits up to 1 second
"""

import threading

from anansi.collector.collect_set import CollectorSet
from anansi.collector.local_collector import get_local_collectors
from anansi.collector.remote_collector import RemoteCollector
from anansi.common.logging import get_logger
from anansi.common.singleton import ThreadSafeSingleton
from anansi.common.timer import sync_wait_until
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.graph.graph import Graph
from anansi.subscriber.implementations.graph_subscribers import (
    NaiveMemoryStorageGraphSubscriber,
)
from anansi.subscriber.subscriber_collection import SubscriberCollection

LOGGER = get_logger(__name__)


class AnansiCore(ThreadSafeSingleton):
    """
    启动类
    """

    def __init__(self):
        self._mem_storage_subscriber = NaiveMemoryStorageGraphSubscriber(
            name="anansicore-memory-subscriber"
        )
        self._sub_collection: SubscriberCollection = SubscriberCollection(
            subscribers={"anansi": self._mem_storage_subscriber}
        )
        mngr = GlobalConfigManager()
        collect_config = mngr.get_config().collector_config
        subcollectors = []
        subcollectors.extend(
            [
                collector()
                for key, collector in get_local_collectors().items()
                if key not in collect_config.disabled_collectors
            ]
        )
        for slave_config in collect_config.remote_slaves:
            remote_collector = RemoteCollector(slave_config=slave_config)
            if remote_collector.is_valid():
                LOGGER.info(
                    "Remote collector %s is valid, adding to AnansiCore...",
                    slave_config,
                )
                subcollectors.append(remote_collector)
            else:
                LOGGER.info("Remote collector %s is invalid, skipping...", slave_config)

        self._collector_set = CollectorSet(subcollectors=subcollectors)

        self._thread: threading.Thread | None = None
        self._running = 0
        self._stop_event: threading.Event | None = None
        self.lock = threading.RLock()

    def subscriber_collection(self) -> SubscriberCollection:
        return self._sub_collection

    def get_collector_set(self) -> CollectorSet:
        return self._collector_set

    def get_last_graph(self) -> Graph:
        return self._mem_storage_subscriber.latest_graph or Graph()

    def is_running(self) -> bool:
        """Indicate whether the core collection loop is active."""
        with self.lock:
            return self._running > 0

    def start(self):
        with self.lock:
            if self._running:
                LOGGER.warning("AnansiCore is already running.")
                self._running += 1
                return
            self._running = 1
            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self._loop, args=(self._stop_event,), daemon=True
            )
            # Start all collectors
            self._collector_set.start()
            self._thread.start()

    def stop(self):
        with self.lock:
            if not self._running:
                LOGGER.warning("AnansiCore is not running.")
                return
            self._running -= 1
            if self._running > 0:
                LOGGER.info(
                    "AnansiCore won't stop as there are still %d running references.",
                    self._running,
                )
                return
            self._stop_event.set()
            # Stop all collectors
            self._collector_set.stop()

            self._thread.join(timeout=1.0)
            self._thread = None
            self._stop_event = None

    def _loop(self, stop_event: threading.Event):
        try:
            while self._running > 0 and not stop_event.is_set():
                sync_wait_until(
                    stop_event.is_set,
                    timeout=self._sub_collection.expected_next_update_interval,
                    check_interval=0.5,
                )
                if stop_event.is_set():
                    break
                # wake up
                self.trigger_collect()
        except RuntimeError as e:
            LOGGER.error("CollectorOrchestrator loop error:%s", e)

    def trigger_collect(self):
        """
        触发一次采集
        """
        graph = self._collector_set.collect_whole_graph()
        self._sub_collection.notify(graph)

    def trigger_clear(self):
        """
        触发一次手动清理
        """
        self._collector_set.clear()
