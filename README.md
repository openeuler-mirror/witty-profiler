# witty-profiler

`witty-profiler`is a topology discovery and bottleneck analysis framework for AI training and inference systems.

The project continuously collects process, IPC, device, and runtime context data from multiple sources, then fuses those observations into analyzable topology graphs and structured outputs for dependency tracing, resource mapping, and performance investigation.

## Current Positioning

- `collector/python` is the current working reference implementation and already provides the multi-source collection framework.
- `collector/rust` is the Rust implementation under development, intended to provide a higher-performance and more easily embeddable runtime.
- `skills` contains the planned agent-facing skills for invoking the collection framework. This part is still under development.
- `docs` stores shared architecture, interface, and data model documents across implementations.

## Project Capabilities

- Multi-source collection across process relationships, IPC activity, device topology, and runtime context
- Graph fusion that merges heterogeneous collector outputs into a unified entity-relation topology
- Analysis-friendly outputs for bottleneck localization, path reconstruction, topology interpretation, and automated diagnostics
- Planned agent integration through skills that expose collection and profiling workflows to automated agents

## Repository Layout

```text
.
|-- collector/
|   |-- python/   # Current primary implementation of the multi-source collection framework
|   `-- rust/     # Rust collector implementation, under development
|-- docs/         # Shared design documents across implementations
`-- skills/       # Agent-facing skills, under development
```


## Documentation Index

- [Architecture Overview](docs/architecture.md)
- [Collector Interface Draft](docs/collector-interface.md)
- [Data Schema Draft](docs/data-schema.md)
- [Python Reference Implementation](collector/python/README.md)
- [Rust Collector Notes](collector/rust/README.md)
- [Skills Planning Notes](skills/README.md)

## Notes

The Rust implementation and the skills integration are both still under active development. If you are onboarding to the project, start with the Python implementation to understand the current collection workflow.
