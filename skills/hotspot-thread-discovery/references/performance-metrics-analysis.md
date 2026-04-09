# 性能指标分析方法

## 概述

本文档提供系统化的性能指标分析方法论，用于热点线程发现和性能瓶颈诊断。

---

## 核心性能指标体系

### 1. CPU 相关指标

| 指标 | 描述 | 阈值参考 | 分析意义 |
|-----|------|---------|---------|
| CPU Usage | CPU使用率 | >80% 高负载 | 计算密集程度 |
| CPU Time | CPU时间占用 | - | 累计计算开销 |
| User/System Ratio | 用户/内核态比例 | - | 计算类型判断 |
| CPU Affinity | CPU亲和性 | - | NUMA影响评估 |

### 2. 上下文切换指标

| 指标 | 描述 | 阈值参考 | 分析意义 |
|-----|------|---------|---------|
| Voluntary CS | 自愿上下文切换 | - | I/O等待程度 |
| Involuntary CS | 非自愿上下文切换 | >1000/s | CPU竞争程度 |
| CS Rate | 切换速率 | - | 调度开销评估 |

### 3. 内存相关指标

| 指标 | 描述 | 阈值参考 | 分析意义 |
|-----|------|---------|---------|
| RSS | 常驻内存集 | - | 内存占用规模 |
| VMS | 虚拟内存大小 | - | 内存需求规模 |
| Memory Bandwidth | 内存带宽使用 | - | 内存压力评估 |
| Page Faults | 页错误次数 | - | 内存访问模式 |

### 4. NUMA 相关指标

| 指标 | 描述 | 阈值参考 | 分析意义 |
|-----|------|---------|---------|
| Local Access Ratio | 本地访问比例 | <0.7 需关注 | NUMA亲和性 |
| Remote Access Ratio | 远程访问比例 | >0.3 需优化 | 跨NUMA开销 |
| Memory Distribution | 内存分布 | - | NUMA均衡性 |

### 5. Cache 相关指标

| 指标 | 描述 | 阈值参考 | 分析意义 |
|-----|------|---------|---------|
| L1I Miss Rate | L1指令缓存失效率 | >5% 需关注 | 代码局部性 |
| L1D Miss Rate | L1数据缓存失效率 | >10% 需关注 | 数据局部性 |
| LLC Miss Rate | 最后级缓存失效率 | >20% 需优化 | 内存访问效率 |

---

## 指标分析方法论

### 1. 基线对比法

```
异常判定 = (当前值 - 基线值) / 基线值 > 阈值
```

**步骤**：
1. 建立性能基线（正常状态下的指标范围）
2. 收集当前指标数据
3. 计算偏离程度
4. 根据阈值判定异常

### 2. 相关性分析法

识别指标之间的关联关系：

| 相关指标对 | 相关性 | 分析意义 |
|-----------|-------|---------|
| CPU Usage + Involuntary CS | 正相关 | CPU竞争导致调度 |
| Remote Access + LLC Miss | 正相关 | NUMA远程访问影响缓存 |
| Voluntary CS + I/O Wait | 正相关 | I/O阻塞导致切换 |
| Memory Bandwidth + LLC Miss | 正相关 | 内存压力影响缓存 |

### 3. 时间序列分析法

**趋势检测**：
- 短期波动：秒级监控，检测突发异常
- 中期趋势：分钟级监控，检测性能退化
- 长期模式：小时级监控，检测周期性问题

### 4. 多维度交叉分析

```
热点线程判定 = f(CPU使用率, 上下文切换, NUMA亲和性, Cache失效率)
```

**权重建议**：
- CPU Usage: 40%
- Context Switch: 20%
- NUMA Affinity: 20%
- Cache Miss: 20%

---

## 热点线程识别算法

### 算法流程

```
1. 数据收集
   ├── 收集所有线程的CPU使用率
   ├── 收集上下文切换统计
   ├── 收集NUMA访问模式
   └── 收集Cache失效率

2. 预处理
   ├── 过滤空闲线程（CPU < 1%）
   ├── 归一化各指标
   └── 计算综合得分

3. 排序与筛选
   ├── 按综合得分排序
   ├── 选取Top N线程
   └── 分类标记问题类型

4. 根因分析
   ├── 识别主要瓶颈类型
   ├── 关联系统资源状态
   └── 生成优化建议
```

### 综合得分计算

```python
def calculate_hotspot_score(thread_metrics):
    cpu_score = thread_metrics.cpu_usage / 100.0 * 0.4
    
    cs_score = min(thread_metrics.involuntary_cs / 10000.0, 1.0) * 0.2
    
    numa_score = (1 - thread_metrics.local_access_ratio) * 0.2
    
    cache_score = thread_metrics.llc_miss_rate / 100.0 * 0.2
    
    return cpu_score + cs_score + numa_score + cache_score
```

---

## 异常模式识别

### 1. CPU密集型热点

**特征**：
- CPU Usage > 80%
- Involuntary CS 较低
- Cache Miss 正常或较低

**根因**：计算任务繁重

**建议**：优化算法、并行化、卸载到加速器

### 2. I/O密集型热点

**特征**：
- CPU Usage 中等
- Voluntary CS 很高
- I/O Wait 高

**根因**：频繁I/O操作

**建议**：批量处理、异步I/O、缓存优化

### 3. NUMA问题热点

**特征**：
- CPU Usage 中等
- Remote Access Ratio > 30%
- LLC Miss Rate 高

**根因**：NUMA亲和性差

**建议**：调整NUMA策略、绑定CPU、数据本地化

### 4. 锁竞争热点

**特征**：
- CPU Usage 低
- Involuntary CS 很高
- 多线程同步等待

**根因**：锁竞争严重

**建议**：减少锁粒度、使用无锁数据结构、优化临界区

---

## 指标采集工具

### sched_monitor

**采集指标**：
- CPU使用率
- 上下文切换次数
- 运行队列长度
- 调度延迟

### cache_monitor

**采集指标**：
- L1I/L1D Cache失效率
- LLC Cache失效率
- Cache命中次数
- Cache预取效率

### numa_access_info

**采集指标**：
- NUMA节点访问分布
- 本地/远程访问比例
- 内存页面分布
- CPU-内存亲和性

---

## 最佳实践

### 1. 监控频率建议

| 场景 | 采集频率 | 保留周期 |
|-----|---------|---------|
| 实时监控 | 1秒 | 1小时 |
| 性能分析 | 100毫秒 | 10分钟 |
| 问题诊断 | 10毫秒 | 1分钟 |

### 2. 告警阈值设置

```yaml
alerts:
  cpu_usage:
    warning: 70%
    critical: 90%
  
  involuntary_cs:
    warning: 1000/s
    critical: 5000/s
  
  remote_access_ratio:
    warning: 0.3
    critical: 0.5
  
  llc_miss_rate:
    warning: 20%
    critical: 40%
```

### 3. 数据存储建议

- 原始数据：保存详细指标，用于深度分析
- 聚合数据：保存分钟/小时级统计，用于趋势分析
- 异常数据：保存异常时段的完整数据，用于问题回溯

---

## 参考资料

- [context-switch-analysis.md](context-switch-analysis.md) - 上下文切换详细分析
- [hotspot-identification.md](hotspot-identification.md) - 热点识别方法论
- [numa-affinity-analysis.md](numa-affinity-analysis.md) - NUMA亲和性分析
- [thread-classification.md](thread-classification.md) - 线程分类方法
