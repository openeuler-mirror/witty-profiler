"""Base classes for topology graph subscribers.

Provides GraphSubscriber, an ABC for subscribers that specifically handle
Graph objects. All concrete graph subscribers should inherit from this class.

Features:
    - Type-checked to only accept Graph objects
    - Abstract _on_recv() forces implementation in subclasses
    - Automatically sets expected_type to Graph

Usage:
    ```python
    class NaiveMemoryStorageGraphSubscriber(GraphSubscriber):
        def __init__(self):
            super().__init__()
            self.latest_graph = None

        def _on_recv(self, target: Graph):
            self.latest_graph = target
            print(f"Received graph with {len(target.nodes)} nodes")

    # Use with WittyProfilerCore
    subscriber = NaiveMemoryStorageGraphSubscriber()
    core = WittyProfilerCore.get_instance()
    core.subscriber_collection().subscribers["storage"] = subscriber
    ```

Notes:
    Base Subscriber class already provides type checking via notify().
    This class just specializes expected_type and documents the pattern.
"""

from abc import abstractmethod

from witty_profiler.graph.graph import Graph
from witty_profiler.subscriber.subscriber_base import Subscriber


class GraphSubscriber(Subscriber):
    @property
    def expected_type(self) -> type[Graph]:
        return Graph

    @abstractmethod
    def _on_recv(self, target: Graph):
        """Receive and process updated graph data."""
        raise NotImplementedError
