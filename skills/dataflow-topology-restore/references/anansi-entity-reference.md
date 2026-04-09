# Anansi Entity 类型完整参考

本文档提供 Anansi 系统中所有 Entity 类型的完整字段说明。

## 目录

1. [ProcessEntity](#processentity)
2. [ThreadEntity](#threadentity)
3. [SocketEntity](#socketentity)
4. [NPUEntity](#npuentity)
5. [GPUEntity](#gpuentity)
6. [NumaEntity](#numaentity)
7. [NumaSetEntity](#numasetentity)
8. [ContainerEntity](#containerentity)
9. [SharedMemoryEntity](#sharedmemoryentity)
10. [RDMA 相关实体](#rdma-相关实体)
11. [边类型参考](#边类型参考)

---

## ProcessEntity

进程实体，表示系统中的一个进程。

**unique_id 格式**: `pid={pid},ppid={ppid}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `pid` | int | 进程 ID |
| `ppid` | int | 父进程 ID |
| `name` | str | 进程名称 |
| `cmdline` | str | 完整命令行 |
| `entity_namespace` | str | 命名空间 |
| `details` | dict | 扩展信息 |

**示例**:
```json
{
  "entity_type": "ProcessEntity",
  "pid": 1894499,
  "ppid": 1893833,
  "name": "vllm",
  "cmdline": "/usr/local/python3.10.17/bin/python3 /usr/local/python3.10.17/bin/vllm serve ..."
}
```

---

## ThreadEntity

线程实体，表示进程中的一个线程。

**unique_id 格式**: `tid={tid}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `tid` | int | 线程 ID |
| `process` | ProcessEntity | 所属进程 |
| `name` | str | 线程名称 |

---

## SocketEntity

套接字实体，表示网络通信端点。

**unique_id 格式**: `{addr}:{port}({type})`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `socket_type` | str | 套接字类型 (TCP/UDP/UNIX) |
| `socket_addr` | str | 绑定地址 |
| `socket_port` | int | 端口号 |
| `socket_thread` | ThreadEntity | 关联线程 |
| `socket_process` | ProcessEntity | 关联进程 |

---

## NPUEntity

NPU (神经网络处理器) 设备实体。

**unique_id 格式**: `id={id},cpu_affinity={cpu_affinity}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `id` | int | NPU 设备编号 |
| `device_type` | str | 设备类型 (固定为 "npu") |
| `pci_bus_id` | str | PCI 总线 ID |
| `cpu_affinity` | str | CPU 亲和性 (CPU 核心范围) |

**示例**:
```json
{
  "entity_type": "NPUEntity",
  "id": 0,
  "device_type": "npu",
  "pci_bus_id": "0000:C1:00.0",
  "cpu_affinity": "144-167"
}
```

---

## GPUEntity

GPU 设备实体。

**unique_id 格式**: `id={id},pci_bus_id={pci_bus_id}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `id` | int | GPU 设备编号 |
| `device_type` | str | 设备类型 (固定为 "gpu") |
| `pci_bus_id` | str | PCI 总线 ID |
| `cpu_affinity` | str | CPU 亲和性 |
| `numa_affinity` | str | NUMA 亲和性 |

---

## NumaEntity

NUMA 节点实体。

**unique_id 格式**: `numa{numa_id}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `numa_id` | int | NUMA 节点编号 |
| `cpu_set` | str | CPU 核心范围 |
| `memory_set` | str | 内存范围 |
| `numa_stats` | dict | NUMA 统计信息 |
| `mem_info` | dict | 内存信息 |
| `distance_to_all_numa` | dict | 到其他 NUMA 节点的距离 |

**numa_stats 字段说明**:

| 字段 | 描述 |
|-----|------|
| `numa_hit` | 本地内存访问次数 |
| `numa_miss` | 远程内存访问次数 |
| `numa_foreign` | 外来页面数 |
| `interleave_hit` | 交错命中次数 |
| `local_node` | 本地节点访问次数 |
| `other_node` | 远程节点访问次数 |

**distance_to_all_numa 字段说明**:

距离矩阵，表示到其他 NUMA 节点的访问延迟:
- `10`: 本地访问
- `11`: 相邻节点
- `24-32`: 远程节点

---

## NumaSetEntity

NUMA 节点集合实体。

**unique_id 格式**: `{numa_id_str}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `numa_id_str` | str | NUMA ID 列表 (如 "0,2-4,6") |

---

## ContainerEntity

容器实体，表示 Docker/Containerd 容器。

**unique_id 格式**: `{container_id}` (截断为 8 字符)

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `container_id` | str | 容器 ID |
| `container_name` | str | 容器名称 |
| `container_type` | str | 容器类型 (docker/containerd/crio) |

---

## SharedMemoryEntity

共享内存实体。

**unique_id 格式**: `name={name},size={size}`

**字段说明**:

| 字段 | 类型 | 描述 |
|-----|------|------|
| `shm_name` | str | 共享内存名称 |
| `shm_size` | int | 共享内存大小 |

---

## RDMA 相关实体

### RdmaDevice

RDMA 设备实体。

**unique_id 格式**: `dev={dev}`

| 字段 | 类型 | 描述 |
|-----|------|------|
| `dev` | str | 设备名称 (如 mlx5_0) |
| `stats` | dict | 统计信息 |

### RdmaQueuePairEndpoint

RDMA 队列端点实体。

**unique_id 格式**: `qpn={qpn}`

| 字段 | 类型 | 描述 |
|-----|------|------|
| `qpn` | int | Queue Pair Number |
| `pid` | int | 所属进程 ID |
| `pdn` | int | Protection Domain Number |
| `dev` | str | 设备名称 |
| `port` | int | 端口号 |
| `rqpn` | int | 远程 QPN |

### RdmaProtectionDomain

RDMA 保护域实体。

**unique_id 格式**: `pid={pid},pdn={pdn}`

### RdmaMemoryRegion

RDMA 内存区域实体。

**unique_id 格式**: `pid={pid},pdn={pdn},lkey={lkey}`

---

## 边类型参考

### 结构边

| 边类型 | 父类 | 描述 |
|-------|------|------|
| `OwnEdge` | `DeployEdgeP2C` | 所有权关系 (A has B) |
| `BelongEdge` | `DeployEdgeC2P` | 归属关系 (A belongs to B) |
| `RunOnEdge` | `DeployEdgeC2P` | 运行于关系 |
| `HostEdge` | `DeployEdgeP2C` | 承载关系 |

### 数据流边

| 边类型 | 父类 | 描述 |
|-------|------|------|
| `AccessEdge` | `DataStreamEdge` | 访问关系 |
| `SendToSocketEdge` | `DataStreamEdge` | Socket 数据流 |
| `NumaAccessEdge` | `DataStreamEdge` | NUMA 访问 |
| `ConnectToEdge` | `DataStreamEdge` | 连接关系 |
| `IPCEdge` | `DirectedEdge` | 进程间通信 |

### NUMA 相关边

| 边类型 | 描述 |
|-------|------|
| `AffinitativeToNuma` | NPU/GPU 到 NUMA 的亲和关系 |
| `NumaSetContainEdge` | NumaSet 包含 Numa 的关系 |
