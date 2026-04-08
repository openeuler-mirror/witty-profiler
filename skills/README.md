# witty-profiler Skills

The `skills` directory is intended for agent-facing integrations in `witty-profiler`.

Its purpose is to expose the collection framework through simple, reusable skills so agents can trigger profiling workflows and consume structured results without dealing with low-level collector details.

## Available Skills

### 1. [dataflow-topology-restore](dataflow-topology-restore/)
**Purpose**: Reconstruct data flow topologies from witty-profiler (Anansi) system graphs.

**Use Cases**:
- Analyze system topology and communication paths
- Identify NCCL/HCCL communication patterns
- Detect cross-NUMA access patterns
- Understand NPU/GPU data paths

### 2. [hotspot-thread-discovery](hotspot-thread-discovery/)
**Purpose**: Identify performance hotspot threads and processes in AI training systems.

**Use Cases**:
- Analyze CPU usage patterns and detect hotspot threads
- Investigate NUMA affinity issues
- Analyze context switches and contention
- Identify performance bottlenecks in multi-threaded AI workloads
- Diagnose compute, communication, memory, and synchronization bottlenecks

### 3. [bottleneck-identification](bottleneck-identification/)
**Purpose**: Systematic methodology for diagnosing performance bottlenecks in AI training infrastructures using the 7-layer bottleneck framework.

**Use Cases**:
- Comprehensive system performance diagnosis
- Identify bottlenecks across all layers (Compute, Memory, Interconnect, Network, Storage, Control Plane, Data Plane)
- Pattern matching for known bottleneck types
- Generate actionable bottleneck diagnosis reports
- Provide prioritized optimization recommendations

## Status

This part of the project is still under development.
