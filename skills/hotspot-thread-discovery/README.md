# Hotspot Thread Discovery Skill

## 概述

热点线程发现 Skill 用于识别 AI 训练系统中的性能热点线程和进程，帮助定位性能瓶颈。

## 功能特性

### 1. 线程画像
- 分析 ThreadEntity 的 CPU 亲和性
- 分析 NUMA 访问模式
- 分析缓存行为

### 2. 热点检测
- 基于 CPU 使用率识别热点
- 基于上下文切换识别热点
- 基于 NUMA 远端访问识别热点
- 基于缓存缺失识别热点

### 3. 根因定位
- 计算瓶颈识别
- 通信瓶颈识别
- 内存瓶颈识别
- NUMA 瓶颈识别
- 同步瓶颈识别

## 使用方法

### 基本用法

```
分析这个 graph.json 中的热点线程
```

### NUMA 亲和性分析

```
检查这些线程的 NUMA 亲和性，找出跨 NUMA 访问严重的线程
```

### 上下文切换分析

```
分析 sched_monitor 数据，找出上下文切换率最高的线程
```

### 综合分析

```
综合分析 CPU、NUMA、缓存数据，找出性能瓶颈
```

## 数据源

该 Skill 支持以下数据源：

1. **Graph JSON** - witty-profiler 生成的拓扑图
2. **sched_monitor 数据** - 线程调度监控数据
3. **numa_access_info** - NUMA 访问信息
4. **cache_monitor 数据** - 缓存缺失监控数据

## 输出格式

Skill 会生成结构化的分析报告，包括：

- 执行摘要
- 热点线程列表
- 线程分类统计
- NUMA 亲和性分析
- 性能瓶颈分布
- 优化建议优先级

## 参考文档

- [thread-classification.md](references/thread-classification.md) - 线程分类学
- [hotspot-identification.md](references/hotspot-identification.md) - 热点识别规则
- [numa-affinity-analysis.md](references/numa-affinity-analysis.md) - NUMA 亲和性分析
- [context-switch-analysis.md](references/context-switch-analysis.md) - 上下文切换分析

## 适用场景

- AI 训练系统性能分析
- 多线程应用性能优化
- NUMA 架构性能调优
- CPU 调度问题诊断
- 内存访问模式分析

## 限制

- 仅支持 Linux 系统
- 需要 witty-profiler 数据采集
- 需要 root 权限访问某些性能数据

## 版本

- Version: 1.0.0
- Author: witty-profiler team
- Last Updated: 2026-04-07
