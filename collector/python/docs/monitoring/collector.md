# Python Collector Guide

This document is specific to the Python reference implementation under `collector/python`.

## Architecture Overview

```
CollectorSet (Composite)
├── LocalCollectors
│   ├── SocketCollector      # Network connections
│   ├── SharedMemoryCollector # Shared memory regions
│   ├── IPCCollector         # Inter-process communication
│   ├── NumaCollector        # NUMA topology
│   ├── GPUCollector         # GPU devices
│   ├── NPUCollector         # NPU devices
│   ├── RDMACollector        # RDMA network topology
│   ├── ContainerCollector   # Container/Pod context
│   ├── CommonProcessParentCollector # Process tree
│   ├── StaticCollector      # Static seed nodes
│   └── TopCpuUsageCollector # High CPU processes
└── RemoteCollectors
    └── RemoteCollector      # Remote Witty Profiler instances
```

### Core Components

**Collector Base Class** (`src/witty_profiler/collector/collector_base.py`)

All collectors inherit from `Collector` and implement:

- `start()` / `stop()` - Lifecycle management
- `clear()` - Reset internal state
- `_get_seed_graph()` - Return initial seed nodes
- `get_neighbors_with_edges(entity)` - Discover neighbors for BFS expansion
- `supported_source_node_type()` - Entity types this collector can expand

**CollectorSet** (`src/witty_profiler/collector/collect_set.py`)

Aggregates multiple collectors with unified interface:

- BFS traversal from seed nodes
- Automatic deduplication via `GlobalIDManager`
- Dynamic collector addition at runtime
- Thread-safe operation

```python
from witty_profiler.collector import CollectorSet, SocketCollector, SharedMemoryCollector

collectors = CollectorSet(subcollectors=[
    SocketCollector(),
    SharedMemoryCollector(),
])
collectors.start()
graph = collectors.collect_whole_graph()
collectors.stop()
```

### Graph Expansion Strategy

1. **Seed Phase**: Collectors provide initial nodes via `_get_seed_graph()`
2. **BFS Expansion**: For each node, `get_neighbors_with_edges()` discovers neighbors
3. **Deduplication**: `GlobalIDManager` prevents duplicate entities/edges
4. **Iteration Control**: `max_iterations` limits BFS depth
5. **Error Isolation**: Collector failures don't interrupt overall collection

---

## Correct Import Examples

### Compose Specific Collectors

```python
from witty_profiler.collector.collect_set import CollectorSet
from witty_profiler.collector.local_collector.socket_collector import SocketCollector
from witty_profiler.collector.local_collector.shm_collector import SharedMemoryCollector

collectors = CollectorSet(
    subcollectors=[
        SocketCollector(),
        SharedMemoryCollector(),
    ]
)
collectors.start()
graph = collectors.collect_whole_graph()
collectors.stop()
```

### Expand from an Existing Graph

```python
expanded_graph = collectors.expand_since_graph(graph)
```

### Expand from a Single Entity

```python
from witty_profiler.entity.node_entity import ProcessEntity

entity = ProcessEntity.create_ensure_unique_id(pid=1234)
graph = collectors.collect_since(entity)
```

### Add a Collector Dynamically

```python
from witty_profiler.collector.collect_set import CollectorSet
from witty_profiler.collector.local_collector.socket_collector import SocketCollector
from witty_profiler.collector.local_collector.shm_collector import SharedMemoryCollector

collectors = CollectorSet(subcollectors=[SocketCollector()])
collectors.start()
collectors.add_collector(SharedMemoryCollector())
```

## Configuration Hooks

The main configuration controls for the Python collector runtime are still:

- `collector_config.disabled_collectors`
- `collector_config.seed_graph_collectors`
- `collector_config.remote_slaves`

Collector-specific configuration also exists under `collector_config` and `sniffer_config`, depending on the collector.

## Related Documentation

- [Architecture Overview](../architecture/overview.md)
- [Graph Model](../architecture/graph-model.md)
- [Configuration Guide](../configuration.md)
