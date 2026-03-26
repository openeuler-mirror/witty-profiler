# Monitoring Overview

This document describes **entities (nodes)**, **relationships (edges)**, and **metrics** that Anansi can detect and include in its topology graph.

For a concise design-level explanation of how topology is collected and fused, see [Architecture Overview — 拓扑采集原理（High-Level）](../architecture/overview.md#拓扑采集原理high-level).

---

## Entity Types (Graph Nodes)

| Entity Type | Description |
|-------------|-------------|
| `ProcessEntity` | OS process |
| `ThreadEntity` | OS thread |
| `SocketEntity` | Network socket endpoint (TCP/UDP/Unix Domain) |
| `SharedMemoryEntity` | Shared memory region |
| `PipeInodeEntity` | Pipe inode |
| `SysvMsgQueueEntity` | System V message queue |
| `PosixMqEntity` | POSIX message queue |
| `SysvSemEntity` | System V semaphore |
| `NumaEntity` | NUMA node |
| `NumaSetEntity` | Set of NUMA nodes (aggregated as a specific numa access pattern) |
| `DeviceEntity` | Generic hardware device (implemented by GPUEntity and NPUEntity) |
| `NPUEntity` | NPU device |
| `GPUEntity` | GPU device |
| `ContainerEntity` | Container instance |
| `PodEntity` | Kubernetes pod |
| `RdmaQueuePairEndpoint` | RDMA Queue Pair endpoint |
| `RdmaLocalQueuePair` | RDMA local Queue Pair (with process binding) |
| `RdmaProtectionDomain` | RDMA Protection Domain |
| `RdmaDevice` | RDMA device |
| `RdmaMemoryRegion` | RDMA Memory Region |

---

## Edge Types (Graph Relationships)

### Data Flow Edges

| Edge Type | Source → Target | Description |
|-----------|-----------------|-------------|
| `SendToSocketEdge` | Process/Thread → Socket | Process sends data to socket |
| `IPCEdge` | Process → Process | Inter-process communication (pipes, message queues, semaphores, UDS) |
| RDMA edges | RDMA entities | RDMA link and operation relationships |

### Structural Edges

| Edge Type | Source → Target | Description |
|-----------|-----------------|-------------|
| `OwnEdge` | Parent → Child | Ownership relationship |
| `BelongEdge` | Child → Parent | Membership relationship |
| `AccessEdge` | Accessor → Resource | Access relationship |
| `ConnectToEdge` | Entity → Entity | Connection relationship |
| `RunOnEdge` | Entity → Host | Runs-on relationship |
| `HostEdge` | Host → Entity | Hosting relationship |
| `HasAttributeEdge` | Entity → Attribute | Attribute relationship |

### NUMA Affinity Edges

| Edge Type | Source → Target | Description |
|-----------|-----------------|-------------|
| `NumaAccessEdge` | Process → NumaNode | Process affinity to NUMA node |
| `AccessWithProcStatusEdge` | Process → NumaSet | Process NUMA access pattern |

---

## Monitored Metrics (key metrics)

### Network & IPC

#### Socket (TCP/UDP)
- Bytes transferred
- Packets count
- Time range (start/end)

#### Pipe/FIFO
- Bytes transferred
- Read/write count
- Time range (start/end)
- Pipe inode identifier

#### Unix Domain Socket
- Bytes transferred
- Send/recv count
- Time range (start/end)
- Socket type (STREAM/DGRAM)
- Peer inode identifier

#### System V Message Queue
- Message size (bytes)
- Send/recv count
- Message type
- Time range (start/end)
- Message queue ID

#### POSIX Message Queue
- Message size (bytes)
- Send/recv count
- Message priority
- Time range (start/end)
- Message queue descriptor

#### System V Semaphore
- Operation count
- Operation type (wait/signal/zero)
- Operation value
- Operation flags
- Time range (start/end)
- Semaphore set ID

### CPU & Memory

#### CPU Cache Miss
- L1 instruction cache misses
- Last-level cache misses

#### CPU Scheduler Runtime
- Execution time per process/thread on each specific CPU

### RDMA

- Packets sent/received
- Duplicate requests
- RDMA send/receive operations
- Out-of-sequence packets
- Buffer overflow events
- QP resources (qpn, pid, state, type)
- MR resources (mrn, pid, length)

### NPU

- NPU device ID
- PCI Bus ID
- CPU of NPU
- NUMA affinity of NPU
- Process-to-NPU mapping

### GPU

- GPU device ID
- PCI Bus ID
- CPU affinity of GPU
- NUMA affinity of GPU
- Process-to-GPU mapping

### NUMA Monitor

- CPU runtime distribution per NUMA node
- Memory pages per NUMA node
- CPU-memory locality score (computed by cosine similarity of CPU runtime vector and Memory pages distribution vector)
- Context switches statistics
- CPU allowed list configuration
- Memory allowed list configuration

---

## Capabilities

| Domain | Status | Description |
|--------|--------|-------------|
| TCP/UDP socket flows | ✅ | Network socket data flow monitoring |
| Pipe/FIFO communication | ✅ | Anonymous pipe and named FIFO monitoring |
| Unix Domain Socket | ✅ | Local socket communication monitoring |
| System V message queues | ✅ | SysV IPC message queue tracking |
| POSIX message queues | ✅ | POSIX message queue tracking |
| System V semaphores | ✅ | SysV IPC semaphore operation tracking |
| Shared memory access | ✅ | Shared memory region tracking |
| NUMA affinity | ✅ | NUMA node affinity and access patterns |
| NPU process mapping | ✅ | Process-to-NPU device mapping |
| RDMA device stats | ✅ | RDMA packet and operation statistics |
| RDMAQP/MR resources | ✅ | RDMA Queue Pair and Memory Region tracking |
| Container/Pod topology | ✅ | Container and Kubernetes pod topology |
| GPU process mapping | ✅ | Process-to-GPU device mapping |
| torch_npu Python call stack | 🔄 Ongoing | Python function call stacks at torch_npu layer for AI training tracing |
| CANN HBM memory tracking | 🔄 Ongoing | NPU HBM memory allocation/deallocation with OOM fault detection |
| MSPTI communication operator | 🔄 Ongoing | Communication operator dispatch/execution to identify slow NPU cards |
| On-CPU/Off-CPU events | 🔄 Ongoing | CPU scheduling events to detect process contention during AI training |
| Python GC debug data | 🔄 Ongoing | Garbage collection data during AI training iterations |
| Failslow detection | 🔄 Ongoing | Performance degradation pattern detection in AI training workloads |

---

## IPC Communication Monitoring

Anansi provides comprehensive IPC monitoring through multiple eBPF-based sniffers:

### Supported IPC Mechanisms

| Mechanism | Sniffer | Documentation |
|-----------|----------|---------------|
| Pipe/FIFO | `pipe_sniffer` | [pipe.md](profiler/pipe.md) |
| Unix Domain Socket | `unix_socket_sniffer` | [uds.md](profiler/uds.md) |
| System V Message Queue | `sysv_msg_sniffer` | [sysv_msg.md](profiler/sysv_msg.md) |
| POSIX Message Queue | `posix_mq_sniffer` | [posix_mq.md](profiler/posix_mq.md) |
| System V Semaphore | `sysv_sem_sniffer` | [sysv_sem.md](profiler/sysv_sem.md) |

### IPC Graph Construction

All IPC sniffers contribute to the topology graph through:

1. **Entity Creation**: Each IPC resource is represented as a graph node
2. **Edge Creation**: Communication between processes is represented as `IPCEdge`
3. **Metrics Collection**: Operation statistics are attached to entities and edges

### Python Integration

All IPC sniffers provide Python interfaces for programmatic control:

```python
from anansi.tools.ebpftools import (
    PipeSniffer,
    UdsSniffer,
    SysvMsgSniffer,
    PosixMqSniffer,
    SysvSemSniffer
)

# Start sniffers
pipe_sniffer = PipeSniffer(direction="all", interval=2)
pipe_sniffer.start()

# Collect events
events = pipe_sniffer.get_events()

# Stop sniffers
pipe_sniffer.stop()
```

### Configuration

IPC sniffers can be configured via `IPCSnifferEnable` in the configuration:

```python
from anansi.config_manager.configs.sniffer_config import IPCSnifferEnable

ipc_config = IPCSnifferEnable(
    uds_enable=True,
    pipe_enable=True,
    sysv_msg_enable=True,
    posix_mq_enable=True,
    sysv_sem_enable=True
)
```

### Testing

See [IPC Test Guide](../../local/test_ipc_instruction/测试指南.md) for detailed testing instructions and examples.

### Quick Test Examples

```bash
# Pipe test
sudo ./src/anansi/binary/pipe/pipe_sniffer -d all -i 2
ls -la | grep "test"

# UDS test
sudo ./src/anansi/binary/uds/unix_socket_sniffer -d all -i 2
# Run uds_test.py server and client in separate terminals

# System V MQ test
sudo ./src/anansi/binary/sysv_msg/sysv_msg_sniffer -d all -i 2
# Run sysv_msg_test

# POSIX MQ test
sudo ./src/anansi/binary/posix_mq/posix_mq_sniffer -d all -i 2
# Run posix_mq_test

# System V Sem test
sudo ./src/anansi/binary/sysv_sem/sysv_sem_sniffer -i 2
# Run sysv_sem_test
```
