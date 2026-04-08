# Dataflow Topology Restore Skill

## 概述

数据流拓扑还原 Skill 用于从 witty-profiler (Anansi) Graph 中还原系统数据流拓扑，识别关键通信路径和性能瓶颈。

## 功能特性

### 1. Graph 解构
- 识别所有实体类型（Process、Thread、NPU、GPU、NUMA 等）
- 提取实体间的关系和边
- 构建实体分组和层次结构

### 2. 通信路径发现
- 追踪 NPU/GPU 访问路径
- 识别 NUMA 访问模式
- 发现 Socket 通信和 IPC 模式
- 重建 NCCL/HCCL 通信拓扑

### 3. 拓扑重建
- 构建端到端数据流路径
- 识别 Tensor Parallel 数据流模式
- 分析跨 NUMA 访问问题
- 生成可视化拓扑图

### 4. 性能瓶颈识别
- 跨 NUMA 访问检测
- 远程内存访问分析
- 通信热点定位

## 使用方法

### 全面拓扑分析

```
分析这个 graph.json 的数据流拓扑
```

### NPU-NUMA 映射分析

```
识别这个系统中 NPU 和 NUMA 节点的映射关系
```

### 跨 NUMA 访问检测

```
检查是否存在跨 NUMA 访问问题
```

### 通信路径追踪

```
追踪进程间的通信路径
```

## 数据源

该 Skill 支持以下数据源：

1. **Anansi Graph JSON** - witty-profiler 生成的拓扑图
2. **Entity 数据** - 进程、线程、NPU、GPU、NUMA 等实体信息
3. **Edge 数据** - 实体间的关系和通信边

## 输出格式

Skill 会生成结构化的数据流拓扑分析报告，包括：

- 系统概览（容器、进程、NPU、NUMA）
- 进程层级树
- NPU-NUMA 映射表
- 数据流路径图
- 性能瓶颈识别
- 优化建议

## 数据流模式库

### Tensor Parallel 模式
- 多 Worker 进程访问不同 NPU
- NPU 分布在不同 NUMA 节点
- 进程间通过 Socket 或共享内存通信

### 跨 NUMA 访问模式
- CPU-MEM 访问一致性分析
- 远端访问比例计算
- NUMA 亲和性评分

### IPC 通信模式
- Socket 通信识别
- 共享内存访问检测
- 管道通信分析

## 参考文档

- [dataflow-patterns.md](references/dataflow-patterns.md) - AI 训练系统数据流模式详解
- [communication-primitives.md](references/communication-primitives.md) - NCCL/HCCL 通信原语识别方法
- [numa-topology.md](references/numa-topology.md) - NUMA 架构与跨节点访问识别
- [ipc-patterns.md](references/ipc-patterns.md) - 进程间通信模式分析
- [anansi-entity-reference.md](references/anansi-entity-reference.md) - Anansi Entity 类型完整参考

## 适用场景

- AI 训练系统拓扑分析
- 分布式训练通信路径追踪
- NUMA 架构优化
- NPU/GPU 数据路径分析
- 性能瓶颈定位

## 限制

- 需要 witty-profiler 数据采集
- 仅支持 Linux 系统
- 需要完整的 Graph JSON 数据

## 版本

- Version: 1.0.0
- Author: witty-profiler team
- Last Updated: 2026-04-07
