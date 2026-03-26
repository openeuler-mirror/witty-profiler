"""Graph update subscribers for handling topology results.

Observer pattern implementation for receiving and processing topology graphs.
Subscribers are notified after each collection round with the latest graph.

Subscriber Types:
    - BaseSubscriber: Abstract base for all subscribers
    - GraphSubscriber: Specialized for Graph objects
    - ConsoleGraphSubscriber: Print to logger
    - NaiveMemoryStorageGraphSubscriber: Cache latest graph
    - FileGraphDescSubscriber: Persist to file
    - HTTPGraphSubscriber: Export via HTTP POST

Usage:
    ```python
    from witty_profiler.subscriber import SubscriberCollection
    from witty_profiler.subscriber.implementations.graph_subscribers import (
        NaiveMemoryStorageGraphSubscriber,
        ConsoleGraphSubscriber
    )

    # Create collection
    collection = SubscriberCollection(subscribers={
        "storage": NaiveMemoryStorageGraphSubscriber(),
        "console": ConsoleGraphSubscriber()
    })

    # Notify subscribers
    collection.notify(graph)

    # Access results
    latest = collection.subscribers["storage"].latest_graph
    ```

Design:
    - Subscribers register asynchronously
    - Type-checked notify() prevents invalid updates
    - Optional async execution (threading) for blocking operations
    - Configurable update intervals for efficiency
"""

import witty_profiler.subscriber.implementations
from witty_profiler.subscriber.subscriber_collection import SubscriberCollection
