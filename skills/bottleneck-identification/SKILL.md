---
name: bottleneck-identification
description: |
  Diagnose performance bottlenecks in AI training infrastructures using the 7-layer framework
  (Compute, Memory, Interconnect, Network, Storage, Control Plane, Data Plane). Use ONLY when
  the user asks for comprehensive cross-layer performance diagnosis with keywords like "slow",
  "bottleneck", "performance issue", "degradation", "optimization", "diagnosis", "latency",
  "throughput", "efficiency". Use dataflow-topology-restore for Anansi graph/topology reconstruction,
  and hotspot-thread-discovery for thread-level hotspot and system metrics analysis.
---

# 瓶颈问题识别 Skill

本 Skill 教你系统化诊断 AI 训练系统中的性能瓶颈，使用 7 层瓶颈框架分析 Anansi 拓扑图。

## 技能概述

witty-profiler 通过 eBPF 技术采集系统运行时的多维度性能数据。本 Skill 帮助你：

1. **系统化诊断**：使用 7 层瓶颈框架全面分析系统性能
2. **模式匹配**：将 Anansi Graph 特征映射到已知瓶颈模式
3. **证据链构建**：从 Graph 数据中提取支持性证据
4. **报告生成**：生成结构化的瓶颈诊断报告

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
  - [Numa 0](cpus=0-23,mems=0-1,130-255)
  ...
```

**处理步骤**：
1. 读取摘要信息（第一行）
2. 按需读取特定层次的数据
3. 直接进行分析

#### 策略 2：JSON 格式 - 先转换再处理

如果数据源是 JSON 格式，建议先转换为 TXT 格式：

```python
from graph_format_converter import GraphFormatConverter

# 第一步：格式转换
converter = GraphFormatConverter("path/to/graph.json")
compact_data = converter.convert_memory_layer_compact()

# 第二步：渐进式处理转换后的数据
# ... 分析紧凑格式数据
```

**为什么需要转换？**
- JSON 格式包含大量冗余字段（`entity_namespace`, `details`, `device_id` 等）
- 紧凑格式可节省约 80% 的上下文使用量
- 更适合 LLM 分析和人工阅读

### 自动格式检测

使用以下逻辑自动检测数据格式：

```python
def detect_and_process_data(file_path: str):
    """自动检测格式并选择处理策略"""
    
    # 检测文件格式
    if file_path.endswith('.txt'):
        # TXT 格式：直接渐进式处理
        print("检测到 TXT 格式，直接进行渐进式处理...")
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取摘要
            summary_line = f.readline()
            print(summary_line)
            
            # 按需读取数据
            # ...
    elif file_path.endswith('.json'):
        # JSON 格式：建议先转换
        print("检测到 JSON 格式，建议先转换为 TXT 格式...")
        print("使用命令: python graph_format_converter.py graph.json --memory output.txt")
        
        # 或者直接转换
        from graph_format_converter import GraphFormatConverter
        converter = GraphFormatConverter(file_path)
        compact_data = converter.convert_memory_layer_compact()
        print(compact_data)
    else:
        # 尝试自动检测内容
        with open(file_path, 'r', encoding='utf-8') as f:
            first_char = f.read(1)
            if first_char == '{':
                print("检测到 JSON 格式内容...")
                # JSON 处理
            else:
                print("检测到 TXT 格式内容...")
                # TXT 处理
```

## 7 层瓶颈框架

AI 训练系统的性能瓶颈可分为 7 个层次，每层都有特定的瓶颈模式和诊断方法。

### 框架概览

```
┌─────────────────────────────────────────┐
│  Layer 7: Data Plane                    │  数据流处理层
│  - 数据加载、预处理、流水线              │
├─────────────────────────────────────────┤
│  Layer 6: Control Plane                 │  控制平面层
│  - 调度、协调、参数同步                  │
├─────────────────────────────────────────┤
│  Layer 5: Storage                       │  存储层
│  - 文件系统、对象存储、检查点            │
├─────────────────────────────────────────┤
│  Layer 4: Network                       │  网络层
│  - TCP/IP、RDMA、集合通信                │
├─────────────────────────────────────────┤
│  Layer 3: Interconnect                  │  互连层
│  - NUMA、PCIe、NVLink、HCCS              │
├─────────────────────────────────────────┤
│  Layer 2: Memory                        │  内存层
│  - Cache、HBM、DDR、带宽墙               │
├─────────────────────────────────────────┤
│  Layer 1: Compute                       │  计算层
│  - CPU、NPU、GPU、算力利用率             │
└─────────────────────────────────────────┘
```

### 各层详细说明

#### Layer 1: Compute (计算层)

**关注点**: 算力利用率、计算效率

**关键指标**:
- CPU/NPU/GPU 利用率
- 计算吞吐量 (FLOPS)
- 算术强度 (FLOP/Byte)

**典型瓶颈**:
- CPU Starvation: CPU 利用率 < 30%
- NPU Idle: NPU 利用率 < 50%
- Compute Bound: 计算密集但算力不足

**诊断方法**: 参考 [compute-bottlenecks.md](references/compute-bottlenecks.md)

---

#### Layer 2: Memory (内存层)

**关注点**: 内存带宽、缓存效率

**关键指标**:
- 内存带宽利用率
- 缓存命中率 (L1/L2/LLC)
- 内存延迟

**典型瓶颈**:
- Memory Bandwidth Wall: 内存带宽饱和
- Cache Miss Storm: 缓存缺失率高
- HBM Bandwidth Limit: HBM 带宽限制

**诊断方法**: 参考 [memory-bottlenecks.md](references/memory-bottlenecks.md)

---

#### Layer 3: Interconnect (互连层)

**关注点**: 节点内互连带宽

**关键指标**:
- NUMA 远端访问比例
- PCIe 带宽利用率
- NVLink/HCCS 带宽

**典型瓶颈**:
- Cross-NUMA Access: 跨 NUMA 访问频繁
- PCIe Bottleneck: PCIe 带宽饱和
- NVLink Contention: NVLink 竞争

**诊断方法**: 参考 [communication-bottlenecks.md](references/communication-bottlenecks.md)

---

#### Layer 4: Network (网络层)

**关注点**: 节点间通信带宽

**关键指标**:
- 网络吞吐量
- 网络延迟
- 包重传率

**典型瓶颈**:
- Network Congestion: 网络拥塞
- RDMA Bottleneck: RDMA 带宽不足
- Collective Communication: 集合通信瓶颈

**诊断方法**: 参考 [communication-bottlenecks.md](references/communication-bottlenecks.md)

---

#### Layer 5: Storage (存储层)

**关注点**: 存储带宽、I/O 延迟

**关键指标**:
- IOPS
- 存储吞吐量
- I/O 延迟

**典型瓶颈**:
- I/O Bottleneck: I/O 带宽不足
- Checkpoint Bottleneck: 检查点写入慢
- Data Loading Bottleneck: 数据加载慢

**诊断方法**: 参考 [io-bottlenecks.md](references/io-bottlenecks.md)

---

#### Layer 6: Control Plane (控制平面层)

**关注点**: 调度、协调、同步

**关键指标**:
- 调度延迟
- 同步等待时间
- 锁竞争程度

**典型瓶颈**:
- Scheduling Bottleneck: 调度延迟高
- Synchronization Bottleneck: 同步等待长
- Load Imbalance: 负载不均衡

**诊断方法**: 参考 [bottleneck-taxonomy.md](references/bottleneck-taxonomy.md)

---

#### Layer 7: Data Plane (数据流处理层)

**关注点**: 数据流水线效率

**关键指标**:
- 数据加载吞吐量
- 预处理延迟
- 流水线气泡时间

**典型瓶颈**:
- Data Loading Bottleneck: 数据加载慢
- Preprocessing Bottleneck: 预处理慢
- Pipeline Bubble: 流水线气泡

**诊断方法**: 参考 [io-bottlenecks.md](references/io-bottlenecks.md)

---

## 分析方法论：四步瓶颈诊断法

### 第一步：数据收集（渐进式加载）

**重要**：大规模 Graph 可能导致上下文溢出，请使用渐进式加载策略。

#### 渐进式加载策略

**推荐方式：使用紧凑格式转换器**

使用 `skills/graph_format_converter.py` 将 JSON 转换为紧凑格式，可节省约 80% 的上下文：

```python
from graph_format_converter import GraphFormatConverter

converter = GraphFormatConverter("path/to/graph.json")

# 方式1：加载摘要
summary = converter.convert_summary()

# 方式2：按层次加载紧凑格式数据
memory_data = converter.convert_memory_layer_compact()
compute_data = converter.convert_compute_layer_compact()
network_data = converter.convert_network_layer_compact()

# 方式3：按需加载特定类型
entities = converter.convert_entities_by_type(['ProcessEntity', 'ThreadEntity'])
edges = converter.convert_edges_by_type(['NumaAccessEdge'], include_details=True)
```

**命令行使用**：

```bash
# 加载摘要
python scripts/graph_format_converter.py graph.json --summary

# 加载内存层数据（紧凑格式）
python scripts/graph_format_converter.py graph.json --memory

# 加载计算层数据（紧凑格式）
python scripts/graph_format_converter.py graph.json --compute

# 加载网络层数据（紧凑格式）
python scripts/graph_format_converter.py graph.json --network
```

**传统方式：使用数据提取器**

使用 `scripts/bottleneck_data_extractor.py` 中的 `BottleneckDataExtractor` 类：

| 策略 | 方法 | 用途 |
|-----|------|------|
| 先加载摘要 | `extract_summary()` | 了解数据规模，决定后续加载策略 |
| 按层次加载 | `extract_bottleneck_layer_data(layer)` | 只加载特定瓶颈层次的数据 |
| 全量加载 | `extract_all_layers_data()` | 仅适用于小规模 Graph |

**层次参数对照表**：

| 参数值 | 加载内容 |
|-------|---------|
| `compute` | 计算相关实体和边 |
| `memory` | 内存相关实体和边 |
| `interconnect` | 互连相关实体和边 |
| `network` | 网络相关实体和边 |
| `storage` | 存储相关实体和边 |

### 第二步：模式匹配

将 Graph 特征映射到已知瓶颈模式。

**匹配流程**：

```
1. 遍历所有7个层次
2. 对每个层次，检查是否存在该层的瓶颈特征
3. 将匹配到的模式记录下来，标注严重性级别
```

**模式匹配判断标准**：

| 层次 | 检查内容 | 判断条件 |
|-----|---------|---------|
| Compute | NPU利用率 | < 50% → NPU Idle |
| Compute | CPU利用率 | < 30% → CPU Starvation |
| Memory | LLC缓存缺失率 | > 5% → Cache Miss Storm |
| Memory | 内存带宽利用率 | > 80% → Memory Bandwidth Wall |
| Interconnect | NUMA远端访问比例 | > 30% → Cross-NUMA Access |
| Network | 网络延迟 | > 100μs → Network Congestion |
| Storage | I/O等待比例 | > 20% → I/O Bottleneck |

详细的模式识别方法请参考 [references/bottleneck-taxonomy.md](references/bottleneck-taxonomy.md)。

### 第三步：证据链构建

为每个瓶颈模式构建支持性证据。

**证据类型**：

| 证据类型 | 来源 | 示例 |
|---------|------|------|
| 实体级证据 | Entity 属性 | "NPU 0 利用率仅 35%" |
| 边级证据 | Edge 关系 | "进程 A 跨 NUMA 访问比例 45%" |
| 统计证据 | 聚合统计 | "平均 LLC 缓存缺失率 8.5%" |

**证据提取方法**：

1. **实体级证据**：遍历相关类型的 Entity，检查属性值是否异常
2. **边级证据**：遍历相关类型的 Edge，检查关系数据是否异常
3. **统计证据**：对实体或边进行聚合统计，计算平均值、最大值等

### 第四步：报告生成

生成结构化的瓶颈诊断报告。

**报告结构**：

```markdown
# AI 训练系统瓶颈诊断报告

## 执行摘要
- 识别到的瓶颈数量: X
- 严重瓶颈 (P0): Y
- 警告级别 (P1): Z
- 建议关注 (P2): W

## Layer 1: Compute
### 瓶颈模式名称
**严重性**: Critical/Warning/Notice
**描述**: ...
**证据**:
- 证据项 1
- 证据项 2
**优化建议**:
- 建议 1
- 建议 2

## Layer 2: Memory
...

## 优化建议优先级
1. **紧急 (P0)**: ...
2. **重要 (P1)**: ...
3. **建议 (P2)**: ...
```

详细的报告模板请参考 [scripts/bottleneck-report-template.md](scripts/bottleneck-report-template.md)。

---

## 瓶颈模式识别

详细的瓶颈分类学请参考 [bottleneck-taxonomy.md](references/bottleneck-taxonomy.md)。

### 常见瓶颈模式速查表

| 层次 | 瓶颈模式 | 关键特征 | 严重性 |
|-----|---------|---------|--------|
| Compute | CPU Starvation | CPU 利用率 < 30% | 警告 |
| Compute | NPU Idle | NPU 利用率 < 50% | 严重 |
| Compute | Compute Bound | 高 CPU + 高缓存缺失 | 严重 |
| Memory | Memory Bandwidth Wall | 内存带宽 > 80% | 严重 |
| Memory | Cache Miss Storm | LLC Miss > 5% | 警告 |
| Memory | HBM Bandwidth Limit | HBM 带宽饱和 | 严重 |
| Interconnect | Cross-NUMA Access | 远端访问 > 30% | 警告 |
| Interconnect | PCIe Bottleneck | PCIe 带宽 > 90% | 严重 |
| Network | Network Congestion | 网络延迟 > 100μs | 警告 |
| Network | RDMA Bottleneck | RDMA 重传 > 1% | 严重 |
| Storage | I/O Bottleneck | I/O 等待 > 20% | 警告 |
| Storage | Checkpoint Bottleneck | 检查点时间 > 10s | 严重 |
| Control Plane | Scheduling Bottleneck | 调度延迟 > 10ms | 警告 |
| Control Plane | Load Imbalance | 负载差异 > 30% | 警告 |
| Data Plane | Data Loading Bottleneck | 数据加载时间 > 计算时间 | 严重 |

---

## 使用示例

### 示例 1: 全面瓶颈诊断

```
诊断这个 AI 训练系统的性能瓶颈
```

**执行步骤**：
1. 加载 Graph 摘要，了解数据规模
2. 按层次渐进式加载数据
3. 对每个层次进行模式匹配
4. 构建证据链
5. 生成诊断报告

### 示例 2: 特定层次分析

```
分析这个系统的内存层瓶颈
```

**执行步骤**：
1. 只加载内存层数据
2. 匹配内存层瓶颈模式
3. 构建证据链
4. 生成内存层专项报告

### 示例 3: 瓶颈模式验证

```
检查是否存在跨 NUMA 访问瓶颈
```

**执行步骤**：
1. 加载互连层数据
2. 检查 NumaAccessEdge 中的远端访问比例
3. 判断是否超过阈值
4. 输出验证结果

### 示例 4: 生成优化报告

```
生成瓶颈诊断报告并提供优化建议
```

**执行步骤**：
1. 执行全面瓶颈诊断
2. 对每个瓶颈模式，查阅对应参考文档获取优化建议
3. 按优先级排序
4. 生成完整报告

---

## 参考文档

- [bottleneck-taxonomy.md](references/bottleneck-taxonomy.md): 完整瓶颈分类学与识别特征
- [communication-bottlenecks.md](references/communication-bottlenecks.md): 通信瓶颈 10 种模式
- [memory-bottlenecks.md](references/memory-bottlenecks.md): 内存层次瓶颈
- [compute-bottlenecks.md](references/compute-bottlenecks.md): 计算瓶颈
- [io-bottlenecks.md](references/io-bottlenecks.md): I/O 瓶颈识别方法
- [report-generation.md](references/report-generation.md): 瓶颈报告模板与最佳实践

## 辅助脚本

- [bottleneck_data_extractor.py](scripts/bottleneck_data_extractor.py): 数据提取工具
- [bottleneck-report-template.md](scripts/bottleneck-report-template.md): 报告模板
