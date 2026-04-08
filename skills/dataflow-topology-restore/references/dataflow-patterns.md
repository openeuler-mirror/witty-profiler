# AI 训练系统数据流模式

本文档详细描述 AI 训练系统中常见的数据流模式，帮助识别和分析 Anansi Graph 中的通信拓扑。

## 目录

1. [Tensor Parallel 数据流](#tensor-parallel-数据流)
2. [Pipeline Parallel 数据流](#pipeline-parallel-数据流)
3. [Data Parallel 数据流](#data-parallel-数据流)
4. [Parameter Server 数据流](#parameter-server-数据流)
5. [All-Reduce 数据流](#all-reduce-数据流)

---

## Tensor Parallel 数据流

### 模式描述

Tensor Parallelism 将模型切分到多个设备上并行计算，每个设备持有模型参数的子集。设备间需要频繁的 All-Reduce 通信来同步梯度。

### Anansi Graph 识别特征

```
主进程 (vllm serve)
  ├── Worker 进程 0 → AccessEdge → NPU 0
  ├── Worker 进程 1 → AccessEdge → NPU 1
  ├── Worker 进程 2 → AccessEdge → NPU 2
  └── Worker 进程 3 → AccessEdge → NPU 3

NPU 亲和关系:
  NPU 0 → AffinitativeToNuma → NUMA 6
  NPU 1 → AffinitativeToNuma → NUMA 6
  NPU 2 → AffinitativeToNuma → NUMA 4
  NPU 3 → AffinitativeToNuma → NUMA 4
```

### 数据流路径

```
输入数据 → 主进程 → Worker 进程 → NPU → NUMA 内存
                                      ↓
                              All-Reduce 通信 (跨 NPU)
                                      ↓
输出数据 ← 主进程 ← Worker 进程 ← NPU ← NUMA 内存
```

### 性能关注点

1. **跨 NUMA 访问**：Worker 进程的 NUMA 亲和性与 NPU 的 NUMA 亲和性是否匹配
2. **NPU 间通信带宽**：All-Reduce 操作的通信带宽
3. **内存带宽**：每个 Worker 进程的内存访问模式

### 识别方法

```python
def identify_tensor_parallel(graph):
    # 1. 找到主进程
    main_process = find_main_process(graph)
    
    # 2. 找到 Worker 进程 (主进程的子进程)
    workers = find_worker_processes(graph, main_process)
    
    # 3. 检查每个 Worker 是否访问不同的 NPU
    npu_access = analyze_npu_access_pattern(graph, workers)
    
    # 4. 分析 NUMA 亲和性
    numa_affinity = analyze_numa_affinity(graph, npu_access)
    
    return {
        "pattern": "Tensor Parallel",
        "workers": workers,
        "npu_access": npu_access,
        "numa_affinity": numa_affinity
    }
```

---

## Pipeline Parallel 数据流

### 模式描述

Pipeline Parallelism 将模型按层切分，不同层在不同设备上执行，数据按顺序流过各层

### Anansi Graph 识别特征

```
Stage 0 进程 → AccessEdge → NPU 0
Stage 1 进程 → AccessEdge → NPU 1
Stage 2 进程 → AccessEdge → NPU 2
...

进程间通信:
  Stage 0 → SendToSocketEdge/SharedMemory → Stage 1
  Stage 1 → SendToSocketEdge/SharedMemory → Stage 22
  ...
```

### 数据流路径

```
输入 → Stage 0 → NPU 0 → 通信 → Stage 1 → NPU 1 → 通信 → ... → 输出
```

### 性能关注点

1. **阶段间通信延迟**：Socket/共享内存通信的延迟
2. **气泡时间**：各阶段的计算时间差异

---

## Data Parallel 数据流

### 模式描述

Data Parallelism 将数据切分到多个设备，每个设备处理不同的数据子集

### Anansi Graph 识别特征

```
Worker 进程 0 → AccessEdge → NPU 0
Worker 进程 1 → AccessEdge → NPU 1
...

# 每个 Worker 夋理不同的数据分片
# 通信较少
```

### 数据流路径

```
输入数据分片 → Worker 0 → NPU 0 → 独立计算
                → Worker 1 → NPU 1 → 独立计算
                → ...
输出合并
```

---

## Parameter Server 数据流

### 模式描述

Parameter Server 架构使用中心服务器存储和更新参数，Worker 节点从服务器拉取参数

### Anansi Graph 识别特征

```
PS Server 进程 → AccessEdge → NPU 0 (或 CPU)
  ├── Socket 监听

Worker 进程 0 → SendToSocketEdge → PS Server
Worker 进程 1 → SendToSocketEdge → PS Server
...
```

### 数据流路径

```
参数更新: PS Server → NPU 计算 → 存储到内存
参数拉取: Worker → Socket → PS Server → 内存 → Worker 本地计算
```

### 性能关注点

1. **PS Server 總颈**：参数服务器可能成为瓶颈
2. **网络带宽**：Worker 与 PS Server 间的通信带宽

---

## All-Reduce 数据流

### 模式描述

All-Reduce 是分布式训练中最常用的集合通信操作，用于同步梯度

### NCCL/HCCL 通信模式

| 算法 | 描述 | 通信模式 |
|------|------|----------|
| Ring | 礭状环通信 | 点对点 |
| Tree | 树状通信 | 层级化 |
| Hierarchical | 层级化通信 | 主从结构 |

### Anansi Graph 识别特征

```
# Ring All-Reduce: NPU 间点对点通信
NPU 0 ←→ NPU 1 ←→ NPU 2 ←→ NPU 3 ←→ NPU 0

# Tree All-Reduce: 主节点协调
NPU 0 → NPU 1, NPU 2
NPU 2 → NPU 3
NPU 3 → NPU 0, NPU 1
```

### 性能关注点

1. **通信带宽利用率**：NPU 间通信链路的带宽使用情况
2. **延迟**：All-Reduce 操作的延迟

---

## 案例分析：vLLM Tensor Parallel

基于 `references/graph.json` 的实际案例分析

### 系统配置

```
容器: docker-cac9af6aa1ee
主进程: vllm serve (PID: 1894499)
  └── --tensor-parallel-size 4

Worker 进程:
  - PID 1895087 → NPU 0
  - PID 1895088 → NPU 1
  - PID 1895089 → NPU 2
  - PID 1895090 → NPU 3
```

### NPU-NUMA 映射

| NPU ID | NUMA 节点 | CPU 亲和性 |
|--------|----------|-----------|
| 0 | 6 | 144-167 |
| 1 | 6 | 144-167 |
| 2 | 4 | 96-119 |
| 3 | 4 | 96-119 |

### 数据流分析

1. **Worker 进程分布**：4 个 Worker 进程分别访问 4 个 NPU
2. **NUMA 分组**：NPU 0/1 在 NUMA 6，NPU 2/3 在 NUMA 4
3. **潜在问题**：NUMA 6 和 NUMA 4 之间的跨 NUMA 通信可能影响性能

### 优化建议

1. 考虑将 Worker 进程绑定到对应的 NUMA 节点
2. 检查 NUMA 访问模式，确保 CPU 和内存访问的一致性
