# Bottleneck Identification Skill

## 概述

瓶颈问题识别 Skill 提供系统化的方法论来诊断 AI 训练系统中的性能瓶颈，使用 7 层瓶颈框架分析 Anansi 拓扑图。

## 功能特性

### 1. 7 层瓶颈框架
- **Layer 1: Compute** - 计算层瓶颈（CPU Starvation、NPU Idle、Compute Bound）
- **Layer 2: Memory** - 内存层瓶颈（Cache Miss、Memory Bandwidth Wall、HBM 限制）
- **Layer 3: Interconnect** - 互连层瓶颈（Cross-NUMA、PCIe、NVLink）
- **Layer 4: Network** - 网络层瓶颈（Network Congestion、RDMA、集合通信）
- **Layer 5: Storage** - 存储层瓶颈（I/O、Checkpoint、Data Loading）
- **Layer 6: Control Plane** - 控制平面瓶颈（调度、同步、负载均衡）
- **Layer 7: Data Plane** - 数据流处理瓶颈（数据加载、预处理、流水线）

### 2. 模式匹配
- 将 Anansi Graph 特征映射到已知瓶颈模式
- 基于启发式规则识别瓶颈
- 支持多特征组合识别

### 3. 证据链构建
- 从实体属性提取证据
- 从边关系提取证据
- 从统计聚合提取证据

### 4. 报告生成
- 结构化瓶颈诊断报告
- 按优先级排序的优化建议
- 可操作的实施路线图

## 使用方法

### 全面诊断

```
诊断这个 AI 训练系统的性能瓶颈
```

### 特定层次分析

```
分析这个系统的内存层瓶颈
```

### 瓶颈模式验证

```
检查是否存在跨 NUMA 访问瓶颈
```

### 生成报告

```
生成瓶颈诊断报告并提供优化建议
```

## 数据源

该 Skill 支持以下数据源：

1. **Anansi Graph** - witty-profiler 生成的拓扑图
2. **sched_monitor 数据** - 线程调度监控数据
3. **cache_monitor 数据** - 缓存缺失监控数据
4. **numa_access_info** - NUMA 访问信息
5. **网络监控数据** - 网络性能数据

## 输出格式

Skill 会生成结构化的瓶颈诊断报告，包括：

- 执行摘要（系统概况、关键发现）
- 详细分析（按 7 层框架组织）
- 优化建议优先级（P0/P1/P2）
- 实施路线图（分阶段）
- 附录（数据来源、分析方法）

## 瓶颈模式库

### 计算层瓶颈
- CPU Starvation
- NPU Idle
- Compute Bound
- CPU Overload
- NPU Thermal Throttling

### 内存层瓶颈
- Cache Miss Storm
- Memory Bandwidth Wall
- HBM Bandwidth Limit
- Memory Latency Bottleneck
- Memory Capacity Bottleneck

### 通信层瓶颈
- Cross-NUMA Access
- Network Congestion
- RDMA Resource Exhaustion
- PCIe Bandwidth Bottleneck
- NVLink Contention
- HCCS Bandwidth Bottleneck
- All-Reduce Bottleneck
- Parameter Server Bottleneck
- IPC Bottleneck
- Socket Buffer Exhaustion

### 存储层瓶颈
- Disk I/O Bottleneck
- Network I/O Bottleneck
- Data Loading Bottleneck
- Checkpoint Bottleneck
- PCIe Transfer Bottleneck

## 参考文档

- [bottleneck-taxonomy.md](references/bottleneck-taxonomy.md) - 完整瓶颈分类学
- [communication-bottlenecks.md](references/communication-bottlenecks.md) - 通信瓶颈 10 种模式
- [memory-bottlenecks.md](references/memory-bottlenecks.md) - 内存层次瓶颈
- [compute-bottlenecks.md](references/compute-bottlenecks.md) - 计算瓶颈
- [io-bottlenecks.md](references/io-bottlenecks.md) - I/O 瓶颈识别方法
- [report-generation.md](references/report-generation.md) - 瓶颈报告模板与最佳实践

## 适用场景

- AI 训练系统性能诊断
- 分布式训练瓶颈定位
- 多节点系统性能优化
- 硬件资源利用率分析
- 性能回归根因分析

## 限制

- 需要 witty-profiler 数据采集
- 仅支持 Linux 系统
- 部分瓶颈需要特定硬件支持

## 版本

- Version: 1.0.0
- Author: witty-profiler team
- Last Updated: 2026-04-07
