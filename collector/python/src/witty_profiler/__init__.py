"""Witty Profiler: Automated topology detection for AI training/inferencing systems.

A framework for building graph representations of inter-process communication
(IPC) and control flow dependencies in distributed AI workloads. Detects
topology dynamically using multiple kernel-level data collectors.

Core Modules:
    - collector: Topology data collection strategies
    - entity: Graph node definitions (processes, threads, sockets, etc.)
    - edge: Graph edge definitions (communication and structural relationships)
    - graph: Immutable topology graph structure
    - subscriber: Observers for graph updates
    - controller: Lifecycle management and APIs
    - config_manager: Configuration management
    - common: Utilities (logging, singleton, ID management)

Quick Start:
    ```python
    from witty_profiler.controller.witty_profiler_core import WittyProfilerCore

    # Initialize and start collection
    core = WittyProfilerCore.get_instance()
    core.start()

    # Trigger collection
    core.trigger_collect()

    # Get latest topology
    graph = core.get_last_graph()
    print(f"Discovered {len(graph.nodes)} entities")

    # Cleanup
    core.stop()
    ```

Architecture:
    - Singleton controllers orchestrate multiple concurrent collectors
    - Thread-local namespaces for scoped entity creation
    - Global ID manager deduplicates entities across collectors
    - Immutable graph structure ensures thread-safe sharing
    - Subscriber pattern for flexible result handling

Requirements:
    - Python 3.11+
    - Linux kernel with eBPF or similar instrumentation support
    - Compiled socket sniffer binary (build/socket_sniffer)

Note:
    This module does NOT import heavy dependencies (pandas, numpy) by default.
    Import specific modules as needed:
    
    ```python
    # Light imports (no pandas/numpy)
    from witty_profiler.common.logging import get_logger
    from witty_profiler.config_manager.config_manager import GlobalConfigManager
    
    # Heavy imports (requires pandas/numpy)
    from witty_profiler.edge.cpu.numa_sniffer import NumaSniffer
    from witty_profiler.edge.socket.socket_sniffer import SocketSniffer
    ```
"""

__all__ = [
    "collector",
    "entity",
    "edge",
    "graph",
    "subscriber",
    "controller",
    "config_manager",
    "common",
]
