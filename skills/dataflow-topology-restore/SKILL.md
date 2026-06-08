---
name: dataflow-topology-restore
description: |
  Reconstruct data flow topologies from witty-profiler (Anansi) system graphs. Use ONLY when
  keywords like "Anansi graph", "topology", "data flow", "communication path", "NCCL", "HCCL",
  "NUMA mapping", "NPU access", or "inter-process communication" are mentioned, or when the user
  asks how data moves through the AI training system. This is the exclusive skill for "Anansi graph"
  keyword. Use bottleneck-identification for comprehensive performance diagnosis, and
  hotspot-thread-discovery for thread-level hotspot analysis.
---

# 数据流拓扑还原 Skill

本 Skill 教你如何从 witty-profiler (Anansi) Graph 中还原系统数据流拓扑，识别关键通信路径和性能瓶颈。

## 技能概述

witty-profiler 通过 eBPF 技术采集系统运行时的拓扑信息，构建包含实体（Entity）和边（Edge）的图结构。本 Skill 帮助你:

1. **解构 Graph 数据**：识别所有实体类型及其关系
2. **发现通信路径**：追踪数据在进程、线程、NPU/GPU、NUMA 节点间的流动
3. **识别性能瓶颈**：发现跨 NUMA 访问、远程内存访问等问题
4. **还原端到端拓扑**：构建完整的数据流路径图

## 数据源格式处理

### 智能格式检测

本 Skill 支持两种数据格式：
- **TXT 格式**（推荐）：紧凑格式，节省约 80% 上下文
- **JSON 格式**：原始格式，包含完整信息

### 格式处理策略

#### 策略 1：TXT 格式 - 直接渐进式处理

如果数据源已经是 TXT 格式，直接使用渐进式加载策略：

```python
# TXT 格式示例
Graph with 129 nodes and 259 edges
Nodes:
  - Container(cac9af6a)
  - NPU(id=0,cpu_affinity=144-167)
  - ProcessEntity(pid=1893666,ppid=6928,name=containerd-shim)
  ...
Edges:
  - NumaAccessEdge(Process(1893666) -> NumaSet({1-3,6}), similarity=0.85)
  ...
```

**处理步骤**：
1. 读取摘要信息（节点数、边数）
2. 解析节点列表
3. 解析边列表
4. 构建拓扑关系

#### 策略 2：JSON 格式 - 先转换再处理

如果数据源是 JSON 格式，建议先转换为 TXT 格式：

```python
from graph_format_converter import GraphFormatConverter

# 第一步：格式转换
converter = GraphFormatConverter("path/to/graph.json")
compact_data = converter.convert_to_compact_graph(
    entity_types=['ProcessEntity', 'ThreadEntity', 'NPUEntity', 'NumaEntity'],
    edge_types=['AccessEdge', 'NumaAccessEdge', 'SendToSocketEdge'],
    include_details=True
)

# 第二步：渐进式处理转换后的数据
# ... 分析紧凑格式数据
```

**为什么需要转换？**
- JSON 格式的边数据包含完整的 source_node 和 target_node 信息，冗余度高
- 紧凑格式只保留关键信息，节省约 88-92% 的上下文
- 更容易识别数据流路径

### 自动格式检测

使用以下逻辑自动检测数据格式：

```python
def detect_and_process_topology(file_path: str):
    """自动检测格式并选择处理策略"""
    
    # 检测文件格式
    if file_path.endswith('.txt'):
        # TXT 格式：直接渐进式处理
        print("检测到 TXT 格式，直接进行拓扑分析...")
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取摘要
            summary_line = f.readline()
            print(summary_line)
            
            # 解析节点和边
            nodes = []
            edges = []
            current_section = None
            
            for line in f:
                if line.startswith('Nodes:'):
                    current_section = 'nodes'
                elif line.startswith('Edges:'):
                    current_section = 'edges'
                elif line.strip().startswith('- '):
                    if current_section == 'nodes':
                        nodes.append(line.strip()[2:])
                    elif current_section == 'edges':
                        edges.append(line.strip()[2:])
            
            return nodes, edges
    elif file_path.endswith('.json'):
        # JSON 格式：建议先转换
        print("检测到 JSON 格式，建议先转换为 TXT 格式...")
        print("使用命令: python graph_format_converter.py graph.json --nodes --edges output.txt")
        
        # 或者直接转换
        from graph_format_converter import GraphFormatConverter
        converter = GraphFormatConverter(file_path)
        compact_data = converter.convert_to_compact_graph(include_details=True)
        print(compact_data)
```

## 前置知识

### 核心实体类型

| 实体类型 | 描述 | unique_id 格式 |
|---------|------|---------------|
| `ProcessEntity` | 进程 | `pid={pid},ppid={ppid}` |
| `ThreadEntity` | 线程 | `tid={tid}` |
| `NPUEntity` | NPU 设备 | `id={id},cpu_affinity={cpu_affinity}` |
| `GPUEntity` | GPU 设备 | `id={id},pci_bus_id={pci_bus_id}` |
| `NumaEntity` | NUMA 节点 | `numa{numa_id}` |
| `NumaSetEntity` | NUMA 节点集合 | `{numa_id_str}` |
| `SocketEntity` | 网络套接字 | `{addr}:{port}({type})` |
| `ContainerEntity` | 容器 | `{container_id}` |
| `SharedMemoryEntity` | 共享内存 | `name={name},size={size}` |

详细字段说明请参考 [references/anansi-entity-reference.md](references/anansi-entity-reference.md)。

### 核心边类型

**数据流边（DataStreamEdge 子类）**：

| 边类型 | 描述 | 数据流方向 |
|-------|------|-----------|
| `SendToSocketEdge` | Socket 数据流 | Process/Thread → Socket |
| `NumaAccessEdge` | NUMA 访问关系 | Process → NumaSet |
| `AccessEdge` | 设备访问关系 | Process → NPU/GPU |
| `ConnectToEdge` | 连接关系 | Entity → Entity |

**结构边（部署关系）**：

| 边类型 | 描述 | 方向 |
|-------|------|------|
| `HostEdge` | 承载关系 | Container → Process |
| `RunOnEdge` | 运行于关系 | Process → Container |
| `OwnEdge` | 所有权关系 | Parent → Child |
| `BelongEdge` | 归属关系 | Child → Parent |
| `AffinitativeToNuma` | NUMA 亲和关系 | NPU/GPU → NumaSet |
| `NumaSetContainEdge` | NUMA 集合包含 | NumaSet → Numa |

## 分析方法论：三步拓扑还原法

### 第一步：Graph 解构（渐进式加载）

**重要**：大规模 Graph 可能导致上下文溢出，请使用渐进式加载策略。

#### 渐进式加载策略

**推荐方式：使用紧凑格式转换器**

使用 `skills/graph_format_converter.py` 将 JSON 转换为紧凑格式，可节省约 80% 的上下文：

```python
from graph_format_converter import GraphFormatConverter

converter = GraphFormatConverter("path/to/graph.json")

# 方式1：加载摘要
summary = converter.convert_summary()

# 方式2：加载数据流拓扑数据（紧凑格式）
topology_data = converter.convert_to_compact_graph(
    entity_types=['ProcessEntity', 'ThreadEntity', 'NPUEntity', 'NumaEntity'],
    edge_types=['AccessEdge', 'NumaAccessEdge', 'SendToSocketEdge'],
    include_details=True
)

# 方式3：按需加载特定类型
entities = converter.convert_entities_by_type(['ProcessEntity', 'NPUEntity'])
edges = converter.convert_edges_by_type(['NumaAccessEdge'], include_details=True)
```

**命令行使用**：

```bash
# 加载摘要
python scripts/graph_format_converter.py graph.json --summary

# 加载所有节点（紧凑格式）
python scripts/graph_format_converter.py graph.json --nodes

# 加载所有边（紧凑格式）
python scripts/graph_format_converter.py graph.json --edges

# 加载详细信息
python scripts/graph_format_converter.py graph.json --nodes --details
```

**传统方式：使用渐进式加载器**

使用 `scripts/progressive_graph_loader.py` 中的 `GraphLoader` 类：

| 策略 | 方法 | 用途 |
|-----|------|------|
| 先加载摘要 | `load_summary()` | 了解数据规模 |
| 加载数据流数据 | `load_dataflow_topology_data()` | 获取拓扑分析所需数据 |
| 按类型加载 | `load_entities_by_type(types)` | 只加载特定类型实体 |

**数据分组方法**：

加载完成后，按 entity_type 字段对实体进行分组：

| 实体类型 | 筛选条件 |
|---------|---------|
| 进程 | `entity_type == "ProcessEntity"` |
| 线程 | `entity_type == "ThreadEntity"` |
| NPU | `entity_type == "NPUEntity"` |
| NUMA | `entity_type == "NumaEntity"` |

### 第二步：通信路径发现

追踪数据流路径，识别关键通信模式。

**路径发现方法**：

| 目标 | 查找的边类型 | 筛选条件 |
|-----|-------------|---------|
| NPU 访问路径 | `AccessEdge` | target_node 包含 NPUEntity |
| NUMA 访问路径 | `NumaAccessEdge` | - |
| Socket 通信路径 | `SendToSocketEdge` | - |
| IPC 路径 | `IPCEdge` | - |

**路径追踪流程**：

```
1. 从进程/线程实体出发
2. 沿着数据流边追踪
3. 记录经过的所有节点
4. 构建端到端路径
```

### 第三步：拓扑重建

构建端到端数据流路径。

**典型数据流路径**：

```
进程 → 线程 → NPU/GPU → NUMA → 网络
```

**拓扑重建输出**：

1. 进程层级树
2. NPU-NUMA 映射表
3. 数据流路径图
4. 性能瓶颈列表

## 数据流模式识别

### 1. Tensor Parallel 数据流模式

**识别特征**：

| 特征 | 描述 |
|-----|------|
| 多 Worker 进程 | 多个 Worker 访问不同的 NPU |
| NPU 分布 | NPU 分布在不同的 NUMA 节点 |
| 进程间通信 | 通过 Socket 或共享内存通信 |

**典型拓扑结构**：

```
vllm (主进程)
  ├── python3 (Worker 0) → NPU 0 → NUMA 6
  ├── python3 (Worker 1) → NPU 1 → NUMA 6
  ├── python3 (Worker 2) → NPU 2 → NUMA 4
  └── python3 (Worker 3) → NPU 3 → NUMA 4
```

### 2. 跨 NUMA 访问识别

通过 `NumaAccessEdge` 的 `numa_access_info` 字段分析。

**关键字段**：

| 字段 | 描述 | 用途 |
|-----|------|------|
| `cpu_runtime_pct_in_each_numa` | CPU 运行时间分布 | 判断 CPU 亲和性 |
| `mem_pages_in_each_numa` | 内存页分布 | 判断内存亲和性 |
| `cpu_mem_access_cosine_similarity` | CPU-内存一致性分数 | 判断跨 NUMA 程度 |

**判断标准**：

| 一致性分数 | 状态 | 说明 |
|-----------|------|------|
| > 0.8 | 正常 | 本地访问为主 |
| 0.5 - 0.8 | 轻度跨 NUMA | 部分跨 NUMA 访问 |
| 0.3 - 0.5 | 中度跨 NUMA | 显著跨 NUMA 访问 |
| < 0.3 | 严重跨 NUMA | 主要跨 NUMA 访问 |

### 3. 进程间通信模式

**IPC 模式识别**：

| IPC 类型 | 识别方法 | 相关边类型 |
|---------|---------|-----------|
| Socket 通信 | BelongEdge + SendToSocketEdge | Socket → Thread, 数据流 |
| 共享内存 | AccessEdge | Process → SharedMemoryEntity |
| 管道 | IPCEdge | 进程间管道连接 |

## 输出格式

### 数据流拓扑图描述

```markdown
## 数据流拓扑分析报告

### 1. 系统概览
- 容器：{container_name}
- 主进程：{process_name} (PID: {pid})
- NPU 数量：{npu_count}
- NUMA 节点：{numa_nodes}

### 2. 进程层级
{process_tree}

### 3. NPU-NUMA 映射
| NPU ID | NUMA 节点 | CPU 亲和性 |
|--------|----------|-----------|
| {npu_id} | {numa_id} | {cpu_affinity} |

### 4. 数据流路径
{data_flow_paths}

### 5. 性能瓶颈识别
- {bottleneck_1}
- {bottleneck_2}

### 6. 优化建议
- {recommendation_1}
- {recommendation_2}
```

## 案例演示

基于 `references/graph.json` 的完整分析示例,请参考 [references/dataflow-patterns.md](references/dataflow-patterns.md)

## 参考文档

- [dataflow-patterns.md](references/dataflow-patterns.md)：AI 训练系统数据流模式详解
- [communication-primitives.md](references/communication-primitives.md)：NCCL/HCCL 通信原语识别方法
- [numa-topology.md](references/numa-topology.md)：NUMA 架构与跨节点访问识别
- [ipc-patterns.md](references/ipc-patterns.md)：进程间通信模式分析
- [anansi-entity-reference.md](references/anansi-entity-reference.md)：Anansi Entity 类型完整参考

## 辅助脚本

- [parse-anansi-graph.py](scripts/parse-anansi-graph.py)：Graph 解析工具
- [progressive_graph_loader.py](scripts/progressive_graph_loader.py)：渐进式加载工具
