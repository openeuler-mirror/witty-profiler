# Witty Profiler

**Automated data and control stream topology detection for AI training and inferencing systems.**

Witty Profiler builds a graph representation of system dependencies using multiple collectors that detect inter-process communication patterns (sockets, shared memory) and device/topology signals (NUMA/NPU).

## What it does

- Collects topology signals from multiple sources (socket, shared memory, NUMA, GPU/NPU, container context)
- Merges observations into a unified graph model (entities and edges)
- Exposes graph updates through offline runs, HTTP API, and subscribers

## Quick Start

### Installation

```bash
# Basic installation
uv venv .venv --python 3.11
source .venv/bin/activate.sh
uv lock
uv sync

# With HTTP server support
uv sync --group server

# With all
uv sync --group all
```

### Build eBPF tools (required for low-level collectors)

```bash
uv pip install -e . # or uv sync --group server

# build the tools
witty-profiler-build
# or
python -m witty_profiler.tools.build
```

For advanced build options, run `witty-profiler-build --help`.

### Running Witty Profiler

#### Offline batch mode

```bash
witty-profiler --offline --duration 30
```

#### Start HTTP server (default)

```bash
witty-profiler
# API: http://localhost:18090
```

#### Run with custom config

```bash
witty-profiler --config configs/production.json
```

For all runtime options, run `witty-profiler --help`.

### Configuration quick notes

- Configuration priority: CLI arguments > config file > defaults
- Generate a full template config:

```bash
witty-profiler --dump-config local/custom_config.json
```

## Documentation

- **[Getting Started](docs/getting-started/quickstart.md)**: First run and basic workflow
- **[Installation](docs/install.md)**: Environment and dependency setup
- **[Configuration](docs/configuration.md)**: Config schema and runtime options
- **[HTTP Server API](docs/backend/api.md)**: REST endpoints
- **[Architecture Overview](docs/architecture/overview.md)**: System design
- **[Topology Collection Principle (High-Level)](docs/architecture/overview.md#鎷撴墤閲囬泦鍘熺悊high-level)**: Collection flow at design level

## Development

```bash
pytest -v
```

```bash
pylint src
```

```bash
witty-profiler-build
```


