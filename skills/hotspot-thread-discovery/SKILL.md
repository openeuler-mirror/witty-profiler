---
name: hotspot-thread-discovery
description: |
  Identify performance hotspot threads and processes in AI training systems from witty-profiler (Anansi) data. Use this skill when the user wants to analyze CPU usage patterns, detect hotspot threads, investigate NUMA affinity issues, analyze context switches, or identify performance bottlenecks in multi-threaded AI workloads. Automatically trigger when ThreadEntity, ProcessEntity, sched_monitor data, or numa_access_info are detected in the conversation context.
---

# 热点线程发现 Skill

本 Skill 教你如何从 witty-profiler (Anansi) 数据中识别 AI 训练系统中的性能热点线程和进程。

## 技能概述

witty-profiler 通过 eBPF 技术采集系统运行时的线程调度、NUMA 访问、缓存缺失等性能数据。本 Skill 帮助你:

1. **线程画像**：分析 ThreadEntity 的 CPU 亲和性、NUMA 访问模式
2. **热点检测**：基于 CPU 使用率、上下文切换、NUMA 远端访问识别"热"线程
3. **根因定位**：区分计算瓶颈 vs. 通信瓶颈 vs. 内存瓶颈导致的线程热点

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
  - ThreadEntity(tid=1895087,name=python3,process=1894856,cpu_affinity=[0-23],cpu_usage=85.5%)
  - ThreadEntity(tid=1895088,name=python3,process=1894856,cpu_affinity=[0-23],cpu_usage=92.3%)
  - ProcessEntity(pid=1894856,ppid=1894499,name=python3)
  ...
Edges:
  - NumaAccessEdge(Thread(1895087) -> NumaSet({0-2,4}), similarity=0.65)
  ...
```

**处理步骤**：
1. 读取摘要信息
2. 筛选 ThreadEntity 和 ProcessEntity
3. 解析性能指标（CPU 使用率、上下文切换等）
4. 计算热点评分

#### 策略 2：JSON 格式 - 先转换再处理

如果数据源是 JSON 格式，建议先转换为 TXT 格式：

```python
from graph_format_converter import GraphFormatConverter

# 第一步：格式转换
converter = GraphFormatConverter("path/to/graph.json")
compact_data = converter.convert_hotspot_threads_compact()

# 第二步：渐进式处理转换后的数据
# ... 分析紧凑格式数据
```

**为什么需要转换？**
- JSON 格式的 ThreadEntity 包含大量监控数据，但很多字段对热点分析不必要
- 紧凑格式只保留关键性能指标，节省约 75-90% 的上下文
- 更容易识别热点线程

### 自动格式检测

使用以下逻辑自动检测数据格式：

```python
def detect_and_process_hotspot_data(file_path: str):
    """自动检测格式并选择处理策略"""
    
    # 检测文件格式
    if file_path.endswith('.txt'):
        # TXT 格式：直接渐进式处理
        print("检测到 TXT 格式，直接进行热点线程分析...")
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取摘要
            summary_line = f.readline()
            print(summary_line)
            
            # 筛选线程数据
            threads = []
            for line in f:
                if 'ThreadEntity' in line:
                    # 解析线程信息
                    # ThreadEntity(tid=1895087,name=python3,process=1894856,cpu_usage=85.5%)
                    threads.append(line.strip())
            
            return threads
    elif file_path.endswith('.json'):
        # JSON 格式：建议先转换
        print("检测到 JSON 格式，建议先转换为 TXT 格式...")
        print("使用命令: python graph_format_converter.py graph.json --hotspot output.txt")
        
        # 或者直接转换
        from graph_format_converter import GraphFormatConverter
        converter = GraphFormatConverter(file_path)
        compact_data = converter.convert_hotspot_threads_compact()
        print(compact_data)
```

## 前置知识

### 线程分类学

AI 训练系统中的线程可分为以下几类：

| 线程类型 | 特征 | 典型名称模式 | 性能关注点 |
|---------|------|-------------|-----------|
| **计算线程** | 高 CPU 使用率、低上下文切换 | `worker`, `compute`, `forward`, `backward` | CPU 亲和性、缓存命中率 |
| **通信线程** | 中等 CPU、高 Socket/IPC 活动 | `nccl`, `hccl`, `comm`, `send`, `recv` | 网络带宽、跨 NUMA 访问 |
| **驱动线程** | 低 CPU、高内核态时间 | `driver`, `cuda`, `npu` | 设备等待时间 |
| **框架线程** | 低 CPU、高上下文切换 | `main`, `scheduler`, `dataloader` | 锁竞争、同步延迟 |

详细分类标准请参考 [references/thread-classification.md](references/thread-classification.md)。

### 性能指标体系

| 指标类别 | 指标名称 | 数据来源 | 热点判定阈值 |
|---------|---------|---------|-------------|
| **CPU 使用** | CPU 使用率 | sched_monitor | > 80% |
| **CPU 使用** | CPU 时间分布 | sched_monitor (numa_cpu_time) | 跨 NUMA > 30% |
| **上下文切换** | 自愿上下文切换 | /proc/[pid]/status | > 1000/s |
| **上下文切换** | 非自愿上下文切换 | /proc/[pid]/status | > 5000/s |
| **内存访问** | NUMA 远端访问率 | numa_maps | > 20% |
| **内存访问** | 缓存缺失率 | cache_monitor | L1I > 5%, LLC > 2% |

## 分析方法论：三步热点发现法

### 第一步：线程画像（渐进式加载）

**重要**：大规模 Graph 可能导致上下文溢出，请使用渐进式加载策略。

#### 渐进式加载策略

**推荐方式：使用紧凑格式转换器**

使用 `skills/graph_format_converter.py` 将 JSON 转换为紧凑格式，可节省约 80% 的上下文：

```python
from graph_format_converter import GraphFormatConverter

converter = GraphFormatConverter("path/to/graph.json")

# 方式1：加载摘要
summary = converter.convert_summary()

# 方式2：加载热点线程数据（紧凑格式，包含CPU使用率等详细信息）
hotspot_data = converter.convert_hotspot_threads_compact()

# 方式3：按需加载特定类型
threads = converter.convert_entities_by_type(['ThreadEntity'], include_details=True)
processes = converter.convert_entities_by_type(['ProcessEntity'])
```

**命令行使用**：

```bash
# 加载摘要
python scripts/graph_format_converter.py graph.json --summary

# 加载热点线程数据（紧凑格式）
python scripts/graph_format_converter.py graph.json --hotspot

# 加载线程详细信息
python scripts/graph_format_converter.py graph.json --nodes --details | grep ThreadEntity
```

**传统方式：使用渐进式加载器**

使用 `scripts/progressive_loader.py` 中的 `GraphLoader` 类：

| 策略 | 方法 | 用途 |
|-----|------|------|
| 先加载摘要 | `load_summary()` | 了解数据规模 |
| 加载热点数据 | `load_hotspot_thread_data()` | 获取热点分析所需数据 |
| 按类型加载 | `load_entities_by_type(types)` | 只加载特定类型实体 |

**线程画像构建**：

对每个 ThreadEntity，提取以下信息：

| 字段 | 来源 | 用途 |
|-----|------|------|
| tid | thread_entity.tid | 线程标识 |
| name | thread_entity.name | 线程名称 |
| process | thread_entity.process_pid | 所属进程 |
| cpu_affinity | thread_entity.cpu_affinity | CPU 亲和性 |
| numa_access | numa_access_info | NUMA 访问模式 |
| cpu_usage | sched_monitor | CPU 使用率 |
| ctx_switches | sched_monitor | 上下文切换 |

### 第二步：热点检测

基于多维度指标识别热点线程。

**热点评分规则**：

| 检查项 | 条件 | 得分 | 说明 |
|-------|------|------|------|
| CPU 使用率 | > 80% | +2 | 高 CPU 使用 |
| 上下文切换率 | > 5000/s | +1 | 高调度开销 |
| NUMA 远端访问 | > 20% | +2 | 跨 NUMA 访问 |
| LLC 缓存缺失 | > 2% | +1 | 缓存效率低 |

**热点判定标准**：

| 总分 | 状态 | 说明 |
|-----|------|------|
| ≥ 5 | 严重热点 | 需要立即处理 |
| 3-4 | 中度热点 | 需要关注 |
| 1-2 | 轻度热点 | 建议优化 |
| 0 | 正常 | 无需处理 |

**检测流程**：

```
1. 遍历所有线程
2. 对每个线程，按评分规则计算得分
3. 记录触发得分的原因
4. 按总分排序，选取热点线程
```

### 第三步：根因定位

区分不同类型的性能瓶颈。

**根因判断逻辑**：

| 条件组合 | 瓶颈类型 | 说明 |
|---------|---------|------|
| CPU > 80% 且 LLC Miss < 1% | 计算瓶颈 | CPU 使用高且缓存友好 |
| CPU > 80% 且 LLC Miss > 1% | 内存瓶颈 | CPU 使用高但缓存缺失严重 |
| 自愿切换 > 非自愿切换 且有 IPC | 通信瓶颈 | 自愿切换多且存在 IPC 活动 |
| 自愿切换 > 非自愿切换 且无 IPC | 同步瓶颈 | 自愿切换多但无 IPC，可能是锁竞争 |
| NUMA 远端访问 > 20% | NUMA 瓶颈 | 跨 NUMA 访问比例高 |

**根因定位流程**：

```
1. 检查 CPU 使用率是否异常高
   - 是 → 进一步检查缓存缺失率
     - 缓存缺失低 → 计算瓶颈
     - 缓存缺失高 → 内存瓶颈

2. 检查上下文切换模式
   - 自愿切换多 → 检查是否有 IPC 活动
     - 有 IPC → 通信瓶颈
     - 无 IPC → 同步瓶颈

3. 检查 NUMA 访问模式
   - 远端访问比例高 → NUMA 瓶颈
```

## 热点识别启发式规则

详细的启发式规则请参考 [references/hotspot-identification.md](references/hotspot-identification.md)。

### 规则优先级

| 优先级 | 规则名称 | 判定条件 | 置信度 |
|-------|---------|---------|--------|
| P0 | 高 CPU + 高缓存缺失 | CPU > 80% 且 LLC Miss > 5% | 高 |
| P0 | 高 CPU + 跨 NUMA | CPU > 80% 且 Remote NUMA > 30% | 高 |
| P1 | 高上下文切换 | 总切换率 > 5000/s | 中 |
| P1 | NUMA 访问不一致 | CPU-MEM 相似度 < 0.5 | 中 |
| P2 | 高缓存缺失 | LLC Miss > 2% | 低 |

## NUMA 亲和性分析

详细的 NUMA 分析方法请参考 [references/numa-affinity-analysis.md](references/numa-affinity-analysis.md)。

### NUMA 访问模式分类

| 模式 | 特征 | 性能影响 | 优化建议 |
|-----|------|---------|---------|
| **本地访问** | CPU 和内存在同一 NUMA | 最优 | 保持现状 |
| **跨 NUMA 访问** | CPU 和内存跨 NUMA | 中等延迟 | 调整亲和性 |
| **混合访问** | 多个 NUMA 节点访问 | 高延迟 | 数据分区 |
| **远端访问** | 主要访问远端内存 | 严重性能下降 | 紧急优化 |

### NUMA 亲和性评分

**计算方法**：

基于 `numa_affinity_info` 中的两个字段：
- `cpu_runtime_pct_in_each_numa`：CPU 运行时间分布
- `mem_pages_in_each_numa`：内存页分布

计算两者的余弦相似度，得到一致性分数。

**评分标准**：

| 一致性分数 | 评级 | 说明 |
|-----------|------|------|
| > 0.8 | 优秀 | 本地访问为主 |
| 0.5 - 0.8 | 良好 | 部分跨 NUMA |
| 0.3 - 0.5 | 警告 | 显著跨 NUMA |
| < 0.3 | 严重 | 主要跨 NUMA |

## 上下文切换分析

详细的上下文切换分析方法请参考 [references/context-switch-analysis.md](references/context-switch-analysis.md)。

### 上下文切换类型分析

| 切换类型 | 原因 | 典型场景 | 优化方向 |
|---------|------|---------|---------|
| **自愿切换** | 线程主动让出 CPU | I/O 等待、锁等待、sleep | 减少同步等待 |
| **非自愿切换** | 调度器强制切换 | CPU 竞争、时间片耗尽 | 降低 CPU 负载 |

### 上下文切换热点判定

**严重性分级**：

| 切换率 (次/秒) | 严重性 | 说明 |
|--------------|-------|------|
| > 10000 | 严重 | 需要立即处理 |
| 5000 - 10000 | 警告 | 需要关注 |
| 1000 - 5000 | 注意 | 建议优化 |
| < 1000 | 正常 | 无需处理 |

**原因分析**：

| 条件 | 原因 |
|-----|------|
| 自愿切换 > 非自愿切换 × 2 | I/O 或同步等待过多 |
| 非自愿切换 > 自愿切换 × 2 | CPU 竞争激烈 |
| 两者接近 | 混合原因 |

## 输出格式

### 热点线程分析报告

```markdown
# 热点线程分析报告

## 执行摘要
- 分析时间范围: {start_time} - {end_time}
- 总线程数: {total_threads}
- 热点线程数: {hotspot_count}
- 严重问题: {critical_count}

## 热点线程列表

### 1. {thread_name} (TID: {tid})
- **热点评分**: {score}/10
- **所属进程**: {process_name} (PID: {pid})
- **瓶颈类型**: {bottleneck_type}
- **关键指标**:
  - CPU 使用率: {cpu_usage}%
  - 上下文切换率: {ctx_switch_rate}/s
  - NUMA 远端访问: {numa_remote}%
  - LLC 缓存缺失: {llc_miss}%

**问题原因**:
- {reason_1}
- {reason_2}

**优化建议**:
- {recommendation_1}
- {recommendation_2}

### 2. {thread_name_2} (TID: {tid_2})
...

## 线程分类统计

| 线程类型 | 数量 | 平均 CPU | 平均上下文切换 |
|---------|------|---------|--------------|
| 计算线程 | {count} | {avg_cpu}% | {avg_ctx}/s |
| 通信线程 | {count} | {avg_cpu}% | {avg_ctx}/s |
| 驱动线程 | {count} | {avg_cpu}% | {avg_ctx}/s |
| 框架线程 | {count} | {avg_cpu}% | {avg_ctx}/s |

## NUMA 亲和性分析

| NUMA 节点 | 线程数 | 平均亲和性评分 | 问题线程数 |
|----------|-------|--------------|-----------|
| NUMA 0 | {count} | {score} | {problem_count} |
| NUMA 1 | {count} | {score} | {problem_count} |

## 性能瓶颈分布

- 计算瓶颈: {count} 个线程
- 通信瓶颈: {count} 个线程
- 内存瓶颈: {count} 个线程
- NUMA 瓶颈: {count} 个线程
- 同步瓶颈: {count} 个线程

## 优化建议优先级

1. **紧急 (P0)**: {recommendation}
2. **重要 (P1)**: {recommendation}
3. **建议 (P2)**: {recommendation}
```

## 使用示例

### 示例 1: 分析 Graph 中的热点线程

```
分析这个 graph.json 中的热点线程
```

**执行步骤**：
1. 加载 Graph 摘要
2. 加载热点线程数据
3. 构建线程画像
4. 计算热点评分
5. 输出热点线程列表

### 示例 2: 识别 NUMA 亲和性问题

```
检查这些线程的 NUMA 亲和性，找出跨 NUMA 访问严重的线程
```

**执行步骤**：
1. 加载线程和 NUMA 访问数据
2. 计算每个线程的 NUMA 亲和性分数
3. 筛选分数 < 0.5 的线程
4. 输出问题线程列表

### 示例 3: 分析上下文切换热点

```
分析 sched_monitor 数据，找出上下文切换率最高的线程
```

**执行步骤**：
1. 加载 sched_monitor 数据
2. 计算每个线程的上下文切换率
3. 按切换率排序
4. 分析切换原因（自愿 vs 非自愿）
5. 输出分析结果

### 示例 4: 综合性能分析

```
综合分析 CPU、NUMA、缓存数据，找出性能瓶颈
```

**执行步骤**：
1. 加载所有性能数据
2. 对每个线程进行多维度分析
3. 识别瓶颈类型
4. 生成综合报告

## 数据源参考

### sched_monitor 数据

sched_monitor 通过 eBPF 采集线程调度信息：

| 字段名 | 描述 | 用途 |
|-------|------|------|
| `pid` | 线程 ID | 线程标识 |
| `tgid` | 进程 ID | 进程归属 |
| `cpu` | 运行的 CPU | CPU 亲和性分析 |
| `time_ns` | 运行时间 | CPU 使用率计算 |

### numa_access_info 数据

NUMA 访问信息来自 `/proc/[pid]/numa_maps`：

| 字段名 | 描述 | 用途 |
|-------|------|------|
| `total_pages` | 各 NUMA 节点的总页数 | 内存分布分析 |
| `dirty_anon_pages` | 各 NUMA 的脏匿名页 | 写入热点分析 |
| `cpu_runtime_pct_in_each_numa` | 各 NUMA 的 CPU 时间占比 | CPU 亲和性分析 |
| `mem_pages_in_each_numa` | 各 NUMA 的内存页分布 | 内存亲和性分析 |

### cache_monitor 数据

缓存缺失数据来自 PMU 事件：

| 字段名 | 描述 | 用途 |
|-------|------|------|
| `total` | 总缓存访问 | 基准参考 |
| `l1i` | L1 指令缓存缺失 | 代码局部性分析 |
| `llc` | 最后一级缓存缺失 | 内存带宽压力分析 |

## 参考文档

- [thread-classification.md](references/thread-classification.md)：线程分类学详解
- [hotspot-identification.md](references/hotspot-identification.md)：热点线程识别启发式规则
- [numa-affinity-analysis.md](references/numa-affinity-analysis.md)：NUMA 亲和性分析方法
- [context-switch-analysis.md](references/context-switch-analysis.md)：上下文切换与竞争分析
- [performance-metrics-analysis.md](references/performance-metrics-analysis.md)：性能指标分析方法

## 辅助脚本

- [progressive_loader.py](scripts/progressive_loader.py)：渐进式加载工具
- [thread_profile_builder.py](scripts/thread_profile_builder.py)：线程画像构建工具
