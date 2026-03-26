# Graph Model

本文档描述 Witty Profiler 的图模型，包括实体（Entity）、边（Edge）和 ID 语义。

## Graph 结构

Graph 是一个不可变的数据类，包含两个核心字段：

- **nodes** — 实体列表（`list[Entity]`），构造时自动按 `global_id` 去重
- **edges** — 边列表（`list[Edge]`），构造时自动按 `global_id` 去重

构造时，Graph 会自动将边引用的、但不在 nodes 列表中的端点实体补充进来。

## Global ID 语义

每个实体拥有一个全局唯一标识符，格式为：

| 场景 | 格式 | 示例 |
|------|------|------|
| 默认命名空间 | `{类型缩写}({unique_id})` | `Process(pid=1234,ppid=5678)` |
| 指定命名空间 | `{类型缩写}(ns={namespace},{unique_id})` | `Process(ns=192.168.122.1,pid=1234,ppid=5678)` |

- **类型缩写** = 类名去掉 `Entity` 后缀（如 `ProcessEntity` → `Process`）
- 命名空间通过 `EntityNameSpace` 上下文管理器设置，默认命名空间会被省略
- `EntityFactory` 和 `GlobalIDManager` 保证同一 `global_id` 只对应一个实体实例

## 实体类型

实体定义在 [src/witty_profiler/entity/node_entity](../../src/witty_profiler/entity/node_entity) 目录下。

### 基础实体

| 实体类型 | unique_id 格式 | 关键字段 |
|----------|---------------|----------|
| `ProcessEntity` | `pid={pid},ppid={ppid}` | pid, ppid, name, cmdline |
| `ThreadEntity` | `tid={tid}` | tid, process（可选的父进程引用）, name |
| `SocketEntity` | `{addr}:{port}({type})` | socket_type, socket_addr, socket_port, socket_thread, socket_process |
| `SharedMemoryEntity` | `name={name},size={size}` | shm_name, shm_size |
| `PipeInodeEntity` | — | 管道 inode |
| `ContainerEntity` | `{container_id}`（截断为8字符） | container_id, container_name, container_type |
| `PodEntity` | `{pod_id}` | pod_id |

### 设备实体

| 实体类型 | unique_id 格式 | 关键字段 |
|----------|---------------|----------|
| `DeviceEntity` | `{device_id}` | device_id, device_type |
| `GPUEntity` | `id={id},pci_bus_id={pci_bus_id}` | device_type="gpu", pci_bus_id, id, cpu_affinity, numa_affinity |
| `NPUEntity` | `id={id},cpu_affinity={cpu_affinity}` | device_type="npu", pci_bus_id, id, cpu_affinity |

### NUMA 实体

| 实体类型 | unique_id 格式 | 关键字段 |
|----------|---------------|----------|
| `NumaEntity` | `numa{numa_id}` | numa_id, cpu_set, memory_set, numa_stats, mem_info, distance_to_all_numa |
| `NumaSetEntity` | `{numa_id_str}`（花括号包裹） | numa_id_str |

### RDMA 实体

定义在 [src/witty_profiler/entity/node_entity/rdma.py](../../src/witty_profiler/entity/node_entity/rdma.py)：

| 实体类型 | unique_id 格式 | 关键字段 |
|----------|---------------|----------|
| `RdmaQueuePairEndpoint` | `qpn={qpn}` | qpn |
| `RdmaLocalQueuePair` | `pid={pid},qpn={qpn}` | pid, pdn, dev, port, rqpn |
| `RdmaProtectionDomain` | `pid={pid},pdn={pdn}` | pdn, pid, dev |
| `RdmaStatisticPerSecond` | `dev={dev},port={port}` | dev, port, 收发统计 |
| `RdmaDevice` | `dev={dev}` | dev, stats |
| `RdmaMemoryRegion` | `pid={pid},pdn={pdn},lkey={lkey}` | lkey, rkey, mrlen |

## 边类型

边定义在 [src/witty_profiler/edge](../../src/witty_profiler/edge) 目录下。

### 边基类层次

- **Edge** — 基类，包含 `weight` 权重字段和 `merge_other()` 权重累加方法
  - **DirectedEdge** — 有向边，包含 `source_node` 和 `target_node`；global_id 格式为 `"relation: {源gid} {边类型缩写} {目标gid}"`
  - **UndirectedEdge** — 无向边，包含 `nodes` 列表；global_id 格式为 `"[{edge_type}]{[排序后的节点gid]}"`

### 边分类体系

**分类边**（edge_category.py）：

| 类 | 父类 | 用途 |
|----|------|------|
| `DeployEdge` | `DirectedEdge` | 通用部署关系 |
| `DeployEdgeP2C` | `DirectedEdge` | 父→子部署 |
| `DeployEdgeC2P` | `DirectedEdge` | 子→父归属 |
| `DataStreamEdge` | `DirectedEdge` | 数据流 |

**结构边**（structual/）：

| 类 | 父类 | 用途 |
|----|------|------|
| `OwnEdge` | `DeployEdgeP2C` | 所有权（父→子） |
| `BelongEdge` | `DeployEdgeC2P` | 归属关系（子→父） |
| `AccessEdge` | `DataStreamEdge` | 访问关系 |
| `ConnectToEdge` | `DataStreamEdge` | 连接关系 |
| `RunOnEdge` | `DeployEdgeC2P` | 运行于 |
| `HostEdge` | `DeployEdgeP2C` | 承载关系 |
| `HasAttributeEdge` | `DirectedEdge` | 属性关系 |

**领域边**：

| 类 | 模块 | 用途 |
|----|------|------|
| `SendToSocketEdge` | socket/ | 进程/线程 → Socket 数据流 |
| `NumaAccessEdge` | cpu/ | 进程 → NUMA 节点亲和 |
| `AccessWithProcStatusEdge` | cpu/ | 进程 → NumaSet 访问模式 |
| `AffinitativeToNuma` | cpu/ | NUMA 亲和边 |
| `NumaSetContainEdge` | cpu/ | NumaSet 包含关系 |
| `IPCEdge` | ipc/ | 进程间通信 |

此外 `edge/rdma/`、`edge/xpu/`、`edge/docker/` 下包含 RDMA、GPU/NPU 部署和容器关系的边实现。

## 去重与合并

- `EntityFactory` 和 `EdgeFactory` 以 `global_id` 为键去重实例
- Graph 构造时自动去重 nodes 和 edges
- `try_add_edge(merge_enable=True)` 会对同 ID 的重复边调用 `merge_other()` 累加权重

## Graph 操作

### 构造

- **直接构造**：传入实体列表和边列表，Graph 自动去重并补充缺失的端点实体
- **通过 Collector**：调用 `collector.collect_whole_graph()` 返回完整的 Graph 实例

### 查询

- `contains_node(entity)` / `contains_edge(edge)` — 检查成员关系
- `in` 运算符 — 对 Entity 和 Edge 均适用
- 直接遍历 `graph.nodes` 和 `graph.edges` 列表进行过滤

### 合并与比较

- `graph1 + graph2` — 合并两个图（去重）
- `graph1 <= graph2` — 子图检查
- `graph1 >= graph2` — 超图检查
- `graph1 == graph2` — 等价性检查（双向子图）
- `Graph.merge_graphs([g1, g2, g3])` — 批量合并

### 扩展

- `try_add_node(node)` — 添加节点（已存在则无操作）
- `try_add_edge(edge, merge_enable)` — 添加边及其端点节点，可选权重合并

### 序列化与输出

| 方法 | 输出 | 说明 |
|------|------|------|
| `model_dump()` | `dict` | 调用 `dataclasses.asdict` |
| `model_dump_json()` | `str` | JSON 字符串 |
| `describe()` | `str` | 人类可读的摘要文本，隐藏 `show_in_compressed_graph=False` 的边 |
| `to_mermaid_text()` | `str` | Mermaid 图表文本 |

## 最佳实践

1. **使用命名空间**：在 Collector 中通过 `EntityNameSpace` 上下文管理器创建实体，确保跨 Collector 不冲突
2. **使用工厂创建实体**：通过 `EntityFactory.create_entity()` 创建，自动去重
3. **优先用 `try_add_edge` 而非手动构造**：该方法自动处理端点节点的补充

