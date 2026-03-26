# Output Data Schema

This document describes the graph data that `witty-profiler` currently emits. 

## What the Current Output Looks Like

The main structured output is a serialized `Graph`.

It contains a plain dictionary with two top-level fields:

```json
{
  "nodes": [],
  "edges": []
}
```

## Top-Level Graph Object

The current graph payload has:

- `nodes`: a list of serialized entity objects
- `edges`: a list of serialized edge objects

## Node Shape

Nodes are serialized entity objects. Every node includes a common base set of fields and then adds entity-specific fields.

Common fields present on current entity objects:

- `entity_namespace`
- `entity_type`
- `details`

After that, each entity adds its own fields. For example:

- `ProcessEntity` adds fields such as `pid`, `ppid`, `name`, `cmdline`
- `ThreadEntity` adds fields such as `tid`, `process`, `name`
- `SocketEntity` adds fields such as `socket_type`, `socket_addr`, `socket_port`
- `NumaEntity` adds fields such as `numa_id`, `cpu_set`, `memory_set`
- `GPUEntity` and `NPUEntity` add device-specific identifiers and affinity fields

Example node:

```json
{
  "entity_namespace": "local",
  "entity_type": "ProcessEntity",
  "details": {},
  "pid": 1234,
  "ppid": 1,
  "name": "python",
  "cmdline": "python train.py"
}
```

## Edge Shape

Edges are serialized edge objects. Every edge includes:

- `edge_type`
- `weight`

The rest of the edge shape depends on whether the edge is directed or undirected.

### Directed Edges

Directed edges include:

- `source_node`
- `target_node`

Both fields contain full nested entity objects, not only IDs.

Example:

```json
{
  "edge_type": "SendToSocketEdge",
  "weight": 12.0,
  "source_node": {
    "entity_namespace": "local",
    "entity_type": "ProcessEntity",
    "details": {},
    "pid": 1234,
    "ppid": 1,
    "name": "python",
    "cmdline": "python train.py"
  },
  "target_node": {
    "entity_namespace": "local",
    "entity_type": "SocketEntity",
    "details": {},
    "socket_type": "TCP",
    "socket_addr": "10.0.0.8",
    "socket_port": 8000,
    "socket_thread": null,
    "socket_process": null
  }
}
```

### Undirected Edges

Undirected edges include:

- `nodes`

`nodes` is a list of nested entity objects.

### Edge-Specific Fields

Many edge types carry additional fields beyond `edge_type`, `weight`, and endpoints.

Examples already present in the repository include fields such as:

- `proc_status` on `AccessWithProcStatusEdge`
- transport or traffic metrics on communication-related edges
- device or placement details on deployment-related edges

## Important Characteristic of the Current Payload

The current graph JSON is recursive and denormalized:

- nodes are listed once in `nodes`
- edges embed full node objects again inside `source_node`, `target_node`, or `nodes`

## Identity in the Current Output

Inside the runtime, `Graph`, `Entity`, and `Edge` all rely on `global_id` for deduplication and merging.

However, the current serialized payload does not include `global_id` as a regular field in `model_dump()`. That means:

- deduplication happens before serialization
- consumers receive the merged graph result
- consumers do not currently receive explicit serialized node or edge IDs unless a higher-level protocol adds them

For consumers, the practical identity fields are the combination of:

- `entity_type`
- `entity_namespace`
- the entity-specific key fields for that type


## HTTP Response Wrapper

When the graph is returned through the current FastAPI server, it is wrapped as:

```json
{
  "env": {},
  "content": {
    "nodes": [],
    "edges": []
  }
}
```

`content` is the actual graph payload from `Graph.model_dump()`. `env` contains environment information from the server runtime.

## Minimal Example

The following example matches the style of the current serialized graph more closely than a normalized ID-based schema:

```json
{
  "nodes": [
    {
      "entity_namespace": "local",
      "entity_type": "ProcessEntity",
      "details": {},
      "pid": 1234,
      "ppid": 1,
      "name": "python",
      "cmdline": "python train.py"
    }
  ],
  "edges": [
    {
      "edge_type": "OwnEdge",
      "weight": 0.0,
      "source_node": {
        "entity_namespace": "local",
        "entity_type": "ProcessEntity",
        "details": {},
        "pid": 1234,
        "ppid": 1,
        "name": "python",
        "cmdline": "python train.py"
      },
      "target_node": {
        "entity_namespace": "local",
        "entity_type": "ThreadEntity",
        "details": {},
        "tid": 1235,
        "process": null,
        "name": "python"
      }
    }
  ]
}
```

For a larger real sample, see `collector/python/references/graph.json`.
