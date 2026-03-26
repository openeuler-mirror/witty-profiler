# witty-profiler Architecture

`witty-profiler` collects topology signals from multiple sources, merges them into one graph, and republishes the latest graph to downstream consumers.

In the current implementation, the main sources include:

- process hierarchy
- socket activity
- shared memory
- IPC mechanisms
- NUMA topology and access patterns
- GPU and NPU placement
- RDMA resources
- container context
- remote profiler instances

The result of each collection round is a `Graph` made of `nodes` and `edges`.

## Main Runtime Components

### WittyProfilerCore

`WittyProfilerCore` is the runtime entry point for collection.

Its job is to:

- build the collector set from local collectors and configured remote collectors
- create a `SubscriberCollection` to keep subscribers for receiving graph updates
- start and stop the collection loop
- trigger one collection round on demand

The background loop wakes up according to the subscriber update interval and calls `trigger_collect()`, which runs one full graph collection and publishes the result.

### CollectorSet

`CollectorSet` is the component that combines multiple collectors into one collection pipeline.

It does four important things:

- starts and stops all sub-collectors together
- asks configured collectors for seed graphs
- expands the graph by visiting discovered entities
- merges nodes and edges returned by different collectors


### Collectors

Each collector is responsible for one observation domain. Current collectors in the repository cover local and remote sources, including socket, shared memory, NUMA, GPU, NPU, RDMA, container, static seed, common parent, top CPU usage, IPC, and remote collection scenarios.

Collectors follow the same working pattern:

- prepare their runtime state in `start()`
- release resources in `stop()`
- clear transient state in `clear()`
- provide a seed graph if they are configured as a seed source
- expand known entities through `get_neighbors_with_edges(...)`

### Graph

`Graph` is the shared topology container used across the pipeline.

Its current behavior is important:

- it stores `nodes` and `edges`
- it deduplicates both by `global_id`
- it automatically adds edge endpoints into the node set
- it can be serialized through `model_dump()` and `model_dump_json()`
- it can be rendered as a readable text summary through `describe()`

The graph is the point where heterogeneous observations become one connected view.

### Subscribers

Subscribers are the publication side of the pipeline. After each collection round, `SubscriberCollection` forwards the graph to all registered subscribers.

Current subscribers in the repository include:

- in-memory storage
- console logging
- text file output
- JSON file output
- HTTP POST delivery
- MongoDB output when optional dependencies are installed

The default in-memory subscriber is what backs `WittyProfilerCore.get_last_graph()`.

## End-to-End Flow

The current profiling pipeline can be read as the following sequence:

```text
WittyProfilerCore
    -> build CollectorSet
    -> start collectors
    -> collect seed graphs
    -> expand entities through collectors
    -> merge nodes and edges into Graph
    -> publish Graph to subscribers
```

## Failure Handling

The collection loop is designed to continue when one collector has a local failure.

In the current implementation:

- seed graph failures are logged and skipped
- neighbor discovery failures caused by `OSError` or `ValueError` are logged and skipped
- publication continues through the subscribers that remain healthy

This keeps partial collection results usable even when one observation source is unavailable.

## Example

A typical merged graph fragment in the current system may connect several domains at once:

```text
Process
  -> OwnEdge -> Thread
  -> SendToSocketEdge -> Socket
  -> AccessWithProcStatusEdge -> NumaSet
  -> RunOnEdge -> GPU/NPU
```
