"""Base subscriber interfaces and registry for topology graph updates.

Provides the Subscriber ABC that observes Graph updates from collectors
and processes them (storage, export, visualization). Each subscriber
receives a new Graph after each collection round.

Key Components:
    - Subscriber: ABC for all subscriber implementations
    - SubscriberMeta: Metaclass auto-registering concrete subscriber types
    - SubscriberFactory: Singleton factory for subscriber instantiation

Callback Pattern:
    - _on_recv(target): Abstract method called with Graph object
    - notify(target): Public method with type checking and async support
    - expected_type: Property defining the target object type (default: Graph)

Features:
    - Automatic subscriber registration via SubscriberMeta
    - Type validation before _on_recv() callback
    - Optional async execution via threading (async_notify flag)
    - UUID-based naming for unnamed subscribers
    - Dataclass integration for serialization

Subscriber Configuration:
    - expected_update_interval: How often subscriber expects updates (seconds)
    - async_notify: Run _on_recv() in daemon thread if True
    - name: Unique subscriber identifier (auto-generated if not provided)

Usage:
    ```python
    # Implement concrete subscriber
    class MyGraphSubscriber(Subscriber):
        def _on_recv(self, graph: Graph):
            # Process graph (store, export, etc.)
            print(f"Received graph with {len(graph.nodes)} nodes")

        @property
        def expected_type(self):
            return Graph

    # Create via factory
    factory = SubscriberFactory.get_instance()
    subscriber = factory.create_subscriber({
        "subscriber_type": "MyGraphSubscriber",
        "expected_update_interval": 10.0
    })

    # Or directly
    subscriber = MyGraphSubscriber(expected_update_interval=10.0)
    subscriber.notify(graph)  # Type-checked callback
    ```

Notes:
    Type checking in notify() prevents incorrect target types from reaching
    _on_recv(). Async subscribers don't block graph collection loop.
"""

import threading
import uuid
from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from anansi.common.logging import get_logger
from anansi.common.singleton import ThreadSafeSingleton
from anansi.entity.entity_base import Entity
from anansi.graph.graph import Graph

LOGGER = get_logger(__name__)


class SubscriberMeta(ABCMeta):
    _registry: dict[str, type] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        # 应用dataclass装饰器
        cls = dataclass(cls)

        # 抽象类直接返回
        if hasattr(cls, "__abstractmethods__") and cls.__abstractmethods__:
            return cls
        mcs._registry.setdefault(name, cls)
        return cls

    @classmethod
    def get_registry(cls):
        return cls._registry


class Subscriber(ABC, metaclass=SubscriberMeta):
    """
    Subscriber configuration base class
    """

    subscriber_type: str = field(default="")  # 会被覆盖
    name: str = field(default_factory=lambda: None)
    expected_update_interval: float = field(default=5.0)  # in seconds
    async_notify: bool = field(default=False)  # 是否异步执行on_recv (避免阻塞)

    def __post_init__(self):
        self.subscriber_type = self.__class__.__name__
        if self.name is None:
            self.name = f"{self.subscriber_type}_{uuid.uuid4().hex[:8]}"

    @abstractmethod
    def _on_recv(self, target: Any):
        """
        Callback function when a new entity is received
        """
        raise NotImplementedError

    @property
    def expected_type(self) -> type[Any]:
        return object

    def notify(self, target: Any) -> Optional[threading.Thread]:
        """
        Notify the subscriber with the new entity
        """
        if not isinstance(target, self.expected_type):
            LOGGER.debug(
                "Subscriber %s ignored entity type %s (expected %s)",
                self.__class__.__name__,
                type(target),
                self.expected_type,
            )
            return
        if self.async_notify:
            LOGGER.verbose(
                "Starting async subscriber thread for %s",
                self.__class__.__name__,
            )
            thread = threading.Thread(target=self._on_recv, args=(target,), daemon=True)
            thread.start()
            return thread
        else:
            self._on_recv(target)


class SubscriberFactory(ThreadSafeSingleton):
    """
    Subscriber factory base class
    """

    _instance: "SubscriberFactory" = None

    def create_subscriber(self, config: dict) -> Optional[Subscriber]:
        subscriber_type = config.get("subscriber_type", None)
        if not subscriber_type or subscriber_type not in SubscriberMeta.get_registry():
            LOGGER.error(
                "Invalid subscriber type: %s (available: %s)",
                subscriber_type,
                list(SubscriberMeta.get_registry().keys()),
            )
            return None

        cls = SubscriberMeta.get_registry()[subscriber_type]
        try:
            subscriber = cls(**config)
            return subscriber
        except TypeError as e:
            LOGGER.error("Failed to create subscriber: %s", e)
        return None


def create_subscriber(config) -> Optional[Subscriber]:
    return SubscriberFactory.get_instance().create_subscriber(config)


def get_available_subscriber_types() -> list[str]:
    return list(SubscriberMeta.get_registry().keys())


__all__ = [
    "create_subscriber",
    "get_available_subscriber_types",
]
