# Installation Guide

This guide walks you through installing Anansi and its dependencies.

## System Requirements

### Operating System

- **Linux**: Primary supported platform
  - Ubuntu 20.04+ or equivalent
  - Kernel 4.18+ (5.x+ recommended for eBPF support)
- **Windows**: Limited support (some collectors unavailable)
- **macOS**: Development only (no kernel instrumentation)

### Python Version

- **Python 3.11** or higher (required)
- Python 3.12 supported
- Earlier versions not supported due to type hint requirements

### Hardware

- **CPU**: x86_64 or ARM64 (aarch64)
- **Memory**: 512MB minimum, 2GB+ recommended for large topologies
- **Disk**: 100MB for installation, additional space for logs/data

## Installation Methods

### Method 1: Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager that simplifies dependency management.

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone Anansi repository
git clone https://github.com/yourusername/anansi.git
cd anansi

# Create virtual environment with Python 3.11
uv venv .venv --python 3.11

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Install core dependencies
uv sync

# Install with HTTP server support (optional)
uv sync --group server
```

### Method 2: Using pip

```bash
# Clone repository
git clone https://github.com/yourusername/anansi.git
cd anansi

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Install with HTTP server support
pip install -e ".[server]"
```

### Method 3: From PyPI (when available)

```bash
# Core installation
pip install anansi

# With HTTP server
pip install anansi[server]
```

## Optional Components

### HTTP Server (FastAPI)

For REST API functionality, install the server dependencies:

```bash
uv sync --group server
# or
pip install fastapi uvicorn
```

Without these dependencies, Anansi runs in offline mode only.

### eBPF Tools (C++ Binaries)

The socket collector requires a compiled binary for kernel-level instrumentation:

```bash
# Install build dependencies (Ubuntu/Debian)
sudo apt-get install build-essential cmake libbpf-dev clang llvm bpftool pkg-config libelf-dev zlib1g-dev

# Build all eBPF tools (socket/cache/sched)
anansi-build
# or
python -m anansi.tools.build

# Binaries created under: src/anansi/binary/
```

**Alternative**: Use pre-built binaries from releases (coming soon).

### Development Tools

For contributing or running tests:

```bash
# Install development dependencies
uv sync --group dev

# Includes: pytest, coverage, pylint, black, mypy
```

## Verifying Installation

### Check Python API

```python
# Test imports
python -c "from anansi.controller.anansi_core import AnansiCore; print('✓ Core imported')"
python -c "from anansi.graph.graph import Graph; print('✓ Graph imported')"
python -c "from anansi.collector.local_collector import get_local_collectors; print('✓ Collectors imported')"
```

### Check CLI

```bash
# Show help
python -m anansi --help

# Expected output:
# usage: anansi [-h] [--config CONFIG] [--verify] [--host HOST] [--port PORT]
#               [--offline] [--duration DURATION] [--log-level LOG_LEVEL]
#               [--dump-config DUMP_CONFIG] [--view-graph] [--pid PID]
# ...
```

### Check HTTP Server (if installed)

```bash
# Start server
python -m anansi --host 127.0.0.1 --port 18090 &

# Query API
curl http://127.0.0.1:18090/
# Expected: JSON response with service metadata

# Stop server
pkill -f "python -m anansi"
```

## Troubleshooting

### Python Version Issues

**Error**: `SyntaxError` or `TypeError` during import

**Solution**: Verify Python version:

```bash
python --version  # Must be 3.11+
```

Recreate virtual environment with correct Python:

```bash
uv venv .venv --python 3.11
```

### Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**: Install server dependencies:

```bash
uv sync --group server
```

### Build Failures

**Error**: `CMake not found` or `libbpf-dev not installed`

**Solution**: Install build dependencies:

```bash
# Ubuntu/Debian
sudo apt-get install build-essential cmake libbpf-dev

# RHEL/CentOS
sudo yum install gcc-c++ cmake libbpf-devel

# Arch Linux
sudo pacman -S base-devel cmake libbpf
```

### Permission Issues

**Error**: `Permission denied` when running collectors

**Solution**: Some collectors require elevated privileges:

```bash
# Run with sudo (for kernel instrumentation)
sudo python -m anansi

# Or add CAP_NET_ADMIN capability
sudo setcap cap_net_admin+ep .venv/bin/python
```

## Next Steps

- **[Quick Start Tutorial](quickstart.md)**: Run your first topology collection
- **[Configuration Guide](../configuration.md)**: Customize collector and server settings
- **[Architecture Overview](../architecture/overview.md)**: Understand Anansi's design

## Platform-Specific Notes

### Ubuntu/Debian

```bash
# Install all dependencies
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv build-essential cmake libbpf-dev

# Enable eBPF (if kernel < 5.0)
sudo modprobe bpf
```

### RHEL/CentOS

```bash
# Enable EPEL repository
sudo yum install epel-release

# Install dependencies
sudo yum install python311 gcc-c++ cmake libbpf-devel
```

### Arch Linux

```bash
# All dependencies available in official repos
sudo pacman -S python python-pip base-devel cmake libbpf
```

### Windows (WSL2)

Anansi requires WSL2 on Windows:

```powershell
# Install WSL2
wsl --install

# Inside WSL2 Ubuntu
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv
```

Follow Ubuntu installation instructions within WSL2.
