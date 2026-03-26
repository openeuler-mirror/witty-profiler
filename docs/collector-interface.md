# Collector Interface

This document describes the common collector behavior used in the current `witty-profiler` implementation. 

## Where Collectors Fit

Collectors are the components that turn one observation source into graph data.

Examples already present in the repository include collectors for:

- sockets
- shared memory
- IPC
- NUMA
- GPU and NPU
- RDMA
- container context
- process hierarchy
- static seed nodes
- remote profiler instances

Each collector contributes a partial graph. `CollectorSet` is responsible for combining those partial graphs into one collection result.

## Common Methods

All collectors follow the same method pattern:

```text
start()
stop()
clear()
_get_seed_graph()
get_neighbors_with_edges(entity)
supported_source_node_type()
```

The shared `Collector` base class also provides:

```text
collect_whole_graph(...)
expand_since_graph(graph, ...)
collect_since(entity, ...)
```

These helper methods all use the same traversal logic from bfs.

## Lifecycle

### start()

`start()` prepares the collector for runtime collection.

Depending on the collector, this may mean:

- starting a sniffer or monitor
- opening access to a runtime data source
- preparing a cache or internal state

### stop()

`stop()` releases resources created by `start()`.

Collectors should be safe to stop as part of normal shutdown and should avoid leaving background runtime state behind.

### clear()

`clear()` resets transient state. This is used when the runtime wants to clear previously collected data without rebuilding the whole process.

## Seed Graph Behavior

`_get_seed_graph()` returns the initial graph fragment for that collector.

Not every collector is asked for seeds. `CollectorSet` only calls `_get_seed_graph()` on collectors whose class names are listed in `collector_config.seed_graph_collectors`.

This matters in practice:

- a collector can support graph expansion without being a seed provider
- seed strategy is configured centrally
- seed graph failures are logged and skipped instead of stopping the whole run

## Neighbor Discovery

`get_neighbors_with_edges(entity)` is the main collector method.

It receives one entity and returns:

- a list of neighboring entities
- a list of edges discovered from that entity

The return type in the current code is:

```text
Tuple[list[Entity], list[Edge]]
```

This method is used by the BFS traversal in the shared collector base class.

## Supported Source Types

`supported_source_node_type()` tells `CollectorSet` which entities a collector knows how to expand.

`CollectorSet` uses this to:

- route entities to the right collectors
- avoid calling unrelated collectors
- cache the mapping from entity type to collector list

## Traversal Behavior

- start from a seed graph, an existing graph, or a single entity
- push initial entities into a queue
- pop entities one by one
- call `get_neighbors_with_edges(...)`
- append newly discovered entities back into the queue
- merge duplicate edges by `global_id`
- stop when the queue is empty or `max_iterations` is reached


## What a Collector Should Return

Collectors should return graph data that the rest of the system can merge cleanly.

In the current implementation this means:

- nodes should be valid `Entity` instances
- edges should be valid `Edge` instances
- repeated discoveries should resolve to the same `global_id`
- edge endpoints should match the nodes represented in the result

Collectors do not need to build the whole graph themselves. Returning a correct local fragment is enough, because the graph merge happens centrally.

## Error Handling

During traversal:

- `OSError` and `ValueError` raised by `get_neighbors_with_edges(...)` are logged and skipped
- collector-level seed failures are logged and skipped
- one failing collector does not stop other collectors from contributing data

This keeps the pipeline usable when one data source is temporarily unavailable.

## Composition in CollectorSet

`CollectorSet` is the place where collector behavior becomes one pipeline.

In the current implementation it:

- stores a list of sub-collectors
- starts and stops them together
- merges seed graphs with `Graph.merge_graphs(...)`
- dispatches entities based on supported source types
- allows a collector to be added dynamically through `add_collector(...)`

This design lets a deployment use a small collector subset or a broader multi-source setup without changing the collection entry points.

## Current Expectations for New Collectors

 new collector should fit the existing pipeline in a practical way:

- it should own one observation source clearly
- it should implement the shared lifecycle methods
- it should return entities and edges that merge cleanly with the graph model
- it should tolerate partial visibility
- it should fail locally rather than taking down the whole collection loop

## Small Example

A simplified socket-oriented collector step in the current model looks like this:

```text
input:
  ProcessEntity(pid=1234)

output:
  nodes:
    SocketEntity(...)
    ThreadEntity(...)
  edges:
    SendToSocketEdge(...)
    OwnEdge(...)
```

This is the same pattern used across the existing collector families: each collector expands one known entity into a small graph fragment, and `CollectorSet` merges the result into the whole topology.
