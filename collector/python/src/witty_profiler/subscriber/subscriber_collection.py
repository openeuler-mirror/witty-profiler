"""Aggregates multiple subscribers for coordinated notification.

Provides SubscriberCollection, a composite Subscriber that manages multiple
child subscribers and coordinates their update intervals. Useful for
broadcasting the same Graph to many consumers.

Features:
    - Holds named dictionary of subscribers
    - Aggregates expected_update_interval (max of all subscribers)
    - Broadcasts notify() to all child subscribers
    - Auto-converts dict configs to Subscriber instances via factory

Usage:
    ```python
    # Create collection with multiple subscribers
    collection = SubscriberCollection(subscribers={
        "storage": NaiveMemoryStorageGraphSubscriber(),
        "exporter": CSVExportSubscriber(file_path="output.csv"),
        "logger": LoggingSubscriber()
    })

    # Or with dict configs
    collection = SubscriberCollection(subscribers={
        "storage": {
            "subscriber_type": "NaiveMemoryStorageGraphSubscriber"
        },
        "logger": {
            "subscriber_type": "LoggingSubscriber",
            "expected_update_interval": 10.0
        }
    })

    # Notify all subscribers at once
    collection.notify(graph)  # All subscribers receive graph
    ```

Update Interval Aggregation:
    expected_update_interval = max(all subscriber intervals)
    Ensures WittyProfilerCore wakes up frequently enough for all subscribers.

Notes:
    SubscriberFactory converts dict configs automatically in __post_init__.
    Ignores non-dict, non-Subscriber entries silently.
    Useful for testing with multiple output destinations.
"""

import time
from dataclasses import field
from multiprocessing import RLock
from typing import Any

from witty_profiler.common.logging import get_logger
from witty_profiler.subscriber.subscriber_base import Subscriber, SubscriberFactory

LOGGER = get_logger(__name__)


def get_timestamp() -> float:
    return time.time()


class SubscriberCollection(Subscriber):

    subscribers: dict[str, Subscriber] = field(default_factory=dict)

    def __post_init__(self):
        sub_fact: SubscriberFactory = SubscriberFactory.get_instance()
        self.subscribers: dict[str, Subscriber] = {
            key: (
                subscriber
                if isinstance(subscriber, Subscriber)
                else sub_fact.create_subscriber(subscriber)
            )
            for key, subscriber in self.subscribers.items()
            if isinstance(subscriber, (dict, Subscriber))
        }
        self._lock = RLock()
        return super().__post_init__()

    def _on_recv(self, target: Any) -> None:
        # 转发通知给子订阅者
        with self._lock:
            notify_targets = list(self.subscribers.values())

        for subscriber in notify_targets:
            if not isinstance(target, subscriber.expected_type):
                continue
            try:
                LOGGER.debug(f"Notifying subscriber %s", subscriber.name)
                subscriber.notify(target)
            except Exception as e:
                LOGGER.error(f"Error notifying subscriber {subscriber.name}: {e}")

    def register(
        self, name: str, subscriber: Subscriber, enable_override: bool = False
    ):
        """Register a subscriber to the collection."""
        with self._lock:
            if name in self.subscribers and not enable_override:
                LOGGER.error(f"Subscriber {name} already exists.")
                return
            elif name in self.subscribers and enable_override:
                self.subscribers.pop(name)
            self.subscribers[name] = subscriber

    def unregister_subscriber(self, name: str):
        """Unregister a subscriber."""
        with self._lock:
            if name in self.subscribers:
                del self.subscribers[name]
            LOGGER.info(f"Unregistered subscriber {name}")

    @property
    def expected_next_update_interval(self, default=3.0) -> float:
        """Calculate the expected next update interval based on all subscribers."""
        intervals = []
        with self._lock:
            for subscriber in self.subscribers.values():
                interval = subscriber.expected_update_interval
                if interval is not None and interval > 0:
                    intervals.append(interval)
        if not intervals:
            return default
        return min(intervals)
