# Anansi Documentation

Welcome to documentation for **Anansi**, an automated topology detection framework for AI training and inference systems.

## Overview

Anansi discovers and maps inter-process communication and control dependencies, building real-time graph representations of system topology from kernel-level signals (sockets, shared memory, GPU/NPU device mapping, NUMA affinity, RDMA, CPU profiling, and IPC mechanisms).

## Quick Navigation

### Getting Started
- **[Installation Guide](getting-started/installation.md)** — 环境搭建与依赖安装
- **[Quick Start Tutorial](getting-started/quickstart.md)** — 5 分钟采集第一份拓扑图
- **[Running Anansi](user-guide/running.md)** — CLI 用法、在线/离线模式、编程接口
- **[Configuration Guide](configuration.md)** — Collector、服务、Sniffer 配置

### Core Concepts
- **[Architecture Overview](architecture/overview.md)** — 系统分层设计与组件
- **[Graph Model](architecture/graph-model.md)** — 实体、边、ID 语义与图操作

### API & Integrations
- **[HTTP API Reference](backend/api.md)** — REST 端点与响应格式

### Monitoring
- **[Monitoring Overview](monitoring/overview.md)** — 实体类型、边类型与监控指标

### Profilers (eBPF tools)

#### Network & IPC
- **[Socket Sniffer](profiler/socket.md)** — TCP/UDP socket 监控
- **[Pipe/FIFO Sniffer](profiler/pipe.md)** — 管道和命名管道监控
- **[Unix Domain Socket Sniffer](profiler/uds.md)** — Unix Domain Socket 监控
- **[System V Message Queue Sniffer](profiler/sysv_msg.md)** — System V 消息队列监控
- **[POSIX Message Queue Sniffer](profiler/posix_mq.md)** — POSIX 消息队列监控
- **[System V Semaphore Sniffer](profiler/sysv_sem.md)** — System V 信号量监控

#### CPU & Memory
- **[Cache Miss Monitor](profiler/cache_miss.md)** — CPU cache miss 采样
- **[Sched Monitor](profiler/sched_monitor.md)** — CPU 调度运行时统计

### Visualization
- 离线图导出：`anansi-vis` CLI 支持 HTML / DrawIO / GEXF / Graphviz 格式输出
- 两阶段流水线：Graph → LayoutGraph → Renderer

### Reference
- **[Project File Map](files.md)** — 关键文件与目录导航

## System Requirements

- **Python**: 3.11 or higher
- **OS**: Linux is required for eBPF-based collectors; Windows/macOS are development-only
- **Build Tools (optional)**: CMake, clang/llvm, libbpf, bpftool for eBPF binaries

## Installation (Summary)

```bash
uv venv .venv --python 3.11
uv sync
```

Optional server dependencies:

```bash
uv sync --group server
```

Build eBPF tools (optional):

```bash
anansi-build
# or
python -m anansi.tools.build
```

## Getting Help

- **API Documentation**: See [backend/api.md](backend/api.md) for HTTP endpoints
- **Architecture**: See [architecture/overview.md](architecture/overview.md) for system design

## License

Anansi is released under Apache-2.0 License. See [LICENSE](../LICENSE) for details.

---

**Next Steps**: Start with [Installation Guide](getting-started/installation.md) or [Quick Start Tutorial](getting-started/quickstart.md).
