# 热点线程识别启发式规则

本文档详细描述识别性能热点线程的启发式规则和判定标准。

## 目录

1. [规则体系概述](#规则体系概述)
2. [P0 级规则](#p0-级规则)
3. [P1 级规则](#p1-级规则)
4. [P2 级规则](#p2-级规则)
5. [规则组合应用](#规则组合应用)

---

## 规则体系概述

### 规则优先级

| 优先级 | 含义 | 置信度 | 处理建议 |
|-------|------|--------|---------|
| **P0** | 严重性能问题 | 高 (>90%) | 立即处理 |
| **P1** | 显著性能问题 | 中 (70-90%) | 优先处理 |
| **P2** | 潜在性能问题 | 低 (50-70%) | 建议关注 |

### 规则评分机制

每条规则触发时赋予一定分数，总分用于判断热点程度：

```python
HOTSPOT_THRESHOLDS = {
    "critical": 8,    # 严重热点
    "warning": 5,     # 警告级别
    "notice": 3       # 需要注意
}
```

---

## P0 级规则

### 规则 P0-1: 高 CPU 使用 + 高缓存缺失

**判定条件**:
- CPU 使用率 > 80%
- LLC 缓存缺失率 > 5%

**置信度**: 95%

**问题诊断**:
线程 CPU 使用率高，但大量时间浪费在缓存缺失上，说明数据局部性差。

**性能影响**:
- 内存带宽浪费
- CPU 流水线停顿
- 整体吞吐量下降

**优化建议**:
1. 优化数据结构提高缓存命中率
2. 调整数据访问模式增强局部性
3. 使用缓存友好的算法
4. 考虑数据预取

**示例**:

```python
def check_p0_1(thread):
    if thread["cpu_usage"] > 80 and thread["cache_miss"]["llc_rate"] > 5:
        return {
            "rule": "P0-1",
            "score": 8,
            "severity": "严重",
            "diagnosis": "高 CPU 使用 + 高缓存缺失",
            "impact": f"CPU 使用率 {thread['cpu_usage']:.1f}%, LLC 缓存缺失率 {thread['cache_miss']['llc_rate']:.1f}%",
            "recommendations": [
                "优化数据结构提高缓存命中率",
                "调整数据访问模式增强局部性"
            ]
        }
    return None
```

---

### 规则 P0-2: 高 CPU 使用 + 跨 NUMA 访问

**判定条件**:
- CPU 使用率 > 80%
- NUMA 远端访问比例 > 30%

**置信度**: 92%

**问题诊断**:
线程 CPU 使用率高，但大量访问远端 NUMA 内存，导致高延迟。

**性能影响**:
- 内存访问延迟增加 2-3 倍
- NUMA 互连带宽饱和
- 整体性能下降 20-40%

**优化建议**:
1. 调整 NUMA 亲和性，将线程绑定到数据所在 NUMA 节点
2. 使用 `numactl` 重新分配内存
3. 数据分区减少跨 NUMA 访问
4. 考虑 NUMA 感知的数据结构

**示例**:

```python
def check_p0_2(thread):
    if thread["cpu_usage"] > 80 and thread["numa_access"]["remote_ratio"] > 30:
        return {
            "rule": "P0-2",
            "score": 8,
            "severity": "严重",
            "diagnosis": "高 CPU 使用 + 跨 NUMA 访问",
            "impact": f"CPU 使用率 {thread['cpu_usage']:.1f}%, NUMA 远端访问 {thread['numa_access']['remote_ratio']:.1f}%",
            "recommendations": [
                "调整 NUMA 亲和性",
                "使用 numactl 重新分配内存"
            ]
        }
    return None
```

---

### 规则 P0-3: 极高上下文切换率

**判定条件**:
- 总上下文切换率 > 10000/s
- 非自愿切换占比 > 70%

**置信度**: 90%

**问题诊断**:
线程频繁被调度器抢占，说明 CPU 资源严重竞争。

**性能影响**:
- 调度开销增加
- 缓存失效
- 响应延迟增加

**优化建议**:
1. 减少 CPU 过度订阅
2. 调整线程优先级
3. 使用 CPU 亲和性减少迁移
4. 考虑减少线程数量

**示例**:

```python
def check_p0_3(thread):
    total_switch_rate = thread["ctx_switches"]["total"] / thread["duration"]
    involuntary_ratio = thread["ctx_switches"]["involuntary"] / thread["ctx_switches"]["total"]
    
    if total_switch_rate > 10000 and involuntary_ratio > 0.7:
        return {
            "rule": "P0-3",
            "score": 8,
            "severity": "严重",
            "diagnosis": "极高上下文切换率",
            "impact": f"切换率 {total_switch_rate:.0f}/s, 非自愿切换占比 {involuntary_ratio*100:.1f}%",
            "recommendations": [
                "减少 CPU 过度订阅",
                "调整线程优先级"
            ]
        }
    return None
```

---

## P1 级规则

### 规则 P1-1: 高上下文切换率

**判定条件**:
- 总上下文切换率 > 5000/s

**置信度**: 75%

**问题诊断**:
线程上下文切换频繁，可能存在 I/O 等待或锁竞争。

**性能影响**:
- 调度开销增加
- 响应延迟增加

**优化建议**:
1. 分析切换原因（自愿 vs 非自愿）
2. 减少 I/O 等待
3. 优化锁的使用

**示例**:

```python
def check_p1_1(thread):
    total_switch_rate = thread["ctx_switches"]["total"] / thread["duration"]
    
    if total_switch_rate > 5000:
        return {
            "rule": "P1-1",
            "score": 5,
            "severity": "警告",
            "diagnosis": "高上下文切换率",
            "impact": f"切换率 {total_switch_rate:.0f}/s",
            "recommendations": [
                "分析切换原因",
                "减少 I/O 等待或锁竞争"
            ]
        }
    return None
```

---

### 规则 P1-2: NUMA 访问不一致

**判定条件**:
- CPU-MEM 访问余弦相似度 < 0.5

**置信度**: 78%

**问题诊断**:
线程的 CPU 运行位置和内存访问位置不一致，存在跨 NUMA 访问。

**性能影响**:
- 内存访问延迟增加
- NUMA 互连带宽占用

**优化建议**:
1. 调整 NUMA 亲和性
2. 数据和线程绑定到同一 NUMA

**示例**:

```python
def check_p1_2(thread):
    similarity = thread["numa_access"]["cpu_mem_similarity"]
    
    if similarity < 0.5:
        return {
            "rule": "P1-2",
            "score": 5,
            "severity": "警告",
            "diagnosis": "NUMA 访问不一致",
            "impact": f"CPU-MEM 相似度 {similarity:.2f}",
            "recommendations": [
                "调整 NUMA 亲和性",
                "数据和线程绑定到同一 NUMA"
            ]
        }
    return None
```

---

### 规则 P1-3: 高自愿上下文切换

**判定条件**:
- 自愿上下文切换率 > 1000/s
- 自愿切换占比 > 80%

**置信度**: 72%

**问题诊断**:
线程频繁主动让出 CPU，可能存在大量 I/O 等待或锁等待。

**性能影响**:
- 响应延迟增加
- CPU 利用率下降

**优化建议**:
1. 分析等待原因
2. 使用异步 I/O
3. 减少锁持有时间

**示例**:

```python
def check_p1_3(thread):
    voluntary_rate = thread["ctx_switches"]["voluntary"] / thread["duration"]
    voluntary_ratio = thread["ctx_switches"]["voluntary"] / thread["ctx_switches"]["total"]
    
    if voluntary_rate > 1000 and voluntary_ratio > 0.8:
        return {
            "rule": "P1-3",
            "score": 5,
            "severity": "警告",
            "diagnosis": "高自愿上下文切换",
            "impact": f"自愿切换率 {voluntary_rate:.0f}/s, 占比 {voluntary_ratio*100:.1f}%",
            "recommendations": [
                "分析等待原因",
                "使用异步 I/O 或减少锁持有时间"
            ]
        }
    return None
```

---

## P2 级规则

### 规则 P2-1: 高缓存缺失率

**判定条件**:
- LLC 缓存缺失率 > 2%

**置信度**: 60%

**问题诊断**:
线程的缓存缺失率较高，可能影响性能。

**性能影响**:
- 内存访问延迟增加
- CPU 流水线停顿

**优化建议**:
1. 优化数据局部性
2. 考虑数据预取

**示例**:

```python
def check_p2_1(thread):
    if thread["cache_miss"]["llc_rate"] > 2:
        return {
            "rule": "P2-1",
            "score": 3,
            "severity": "注意",
            "diagnosis": "高缓存缺失率",
            "impact": f"LLC 缓存缺失率 {thread['cache_miss']['llc_rate']:.1f}%",
            "recommendations": [
                "优化数据局部性",
                "考虑数据预取"
            ]
        }
    return None
```

---

### 规则 P2-2: 中等 NUMA 远端访问

**判定条件**:
- NUMA 远端访问比例 > 20%

**置信度**: 65%

**问题诊断**:
线程存在一定比例的跨 NUMA 访问。

**性能影响**:
- 内存访问延迟增加

**优化建议**:
1. 检查 NUMA 亲和性配置
2. 考虑数据分区

**示例**:

```python
def check_p2_2(thread):
    if thread["numa_access"]["remote_ratio"] > 20:
        return {
            "rule": "P2-2",
            "score": 3,
            "severity": "注意",
            "diagnosis": "中等 NUMA 远端访问",
            "impact": f"NUMA 远端访问 {thread['numa_access']['remote_ratio']:.1f}%",
            "recommendations": [
                "检查 NUMA 亲和性配置",
                "考虑数据分区"
            ]
        }
    return None
```

---

## 规则组合应用

### 规则引擎实现

```python
class HotspotDetectionEngine:
    def __init__(self):
        self.p0_rules = [check_p0_1, check_p0_2, check_p0_3]
        self.p1_rules = [check_p1_1, check_p1_2, check_p1_3]
        self.p2_rules = [check_p2_1, check_p2_2]
    
    def detect(self, thread):
        results = []
        total_score = 0
        
        # 检查 P0 规则
        for rule_func in self.p0_rules:
            result = rule_func(thread)
            if result:
                results.append(result)
                total_score += result["score"]
        
        # 检查 P1 规则
        for rule_func in self.p1_rules:
            result = rule_func(thread)
            if result:
                results.append(result)
                total_score += result["score"]
        
        # 检查 P2 规则
        for rule_func in self.p2_rules:
            result = rule_func(thread)
            if result:
                results.append(result)
                total_score += result["score"]
        
        # 判定热点等级
        if total_score >= 8:
            severity = "严重热点"
        elif total_score >= 5:
            severity = "警告热点"
        elif total_score >= 3:
            severity = "潜在热点"
        else:
            severity = "正常"
        
        return {
            "is_hotspot": total_score >= 3,
            "severity": severity,
            "total_score": total_score,
            "triggered_rules": results
        }
```

### 规则组合示例

**示例 1: 计算 + 内存瓶颈**

```
线程 A:
- CPU 使用率: 85%
- LLC 缓存缺失率: 6%
- NUMA 远端访问: 35%

触发规则:
- P0-1: 高 CPU + 高缓存缺失 (8 分)
- P0-2: 高 CPU + 跨 NUMA (8 分)

总分: 16
判定: 严重热点
```

**示例 2: 通信瓶颈**

```
线程 B:
- CPU 使用率: 40%
- 自愿上下文切换率: 1500/s
- NUMA 远端访问: 25%

触发规则:
- P1-3: 高自愿上下文切换 (5 分)
- P2-2: 中等 NUMA 远端访问 (3 分)

总分: 8
判定: 严重热点
```

---

## 规则调优建议

### 阈值调整

根据实际系统特性调整阈值：

```python
# 高性能计算系统 (HPC)
HPC_THRESHOLDS = {
    "cpu_usage": 90,
    "llc_miss": 3,
    "numa_remote": 20,
    "ctx_switch": 5000
}

# 通用服务器
SERVER_THRESHOLDS = {
    "cpu_usage": 80,
    "llc_miss": 5,
    "numa_remote": 30,
    "ctx_switch": 10000
}
```

### 规则权重调整

根据业务优先级调整规则权重：

```python
# 计算密集型应用
COMPUTE_WEIGHTS = {
    "P0-1": 10,  # 高 CPU + 高缓存缺失
    "P0-2": 10,  # 高 CPU + 跨 NUMA
    "P0-3": 6    # 高上下文切换
}

# I/O 密集型应用
IO_WEIGHTS = {
    "P0-1": 6,
    "P0-2": 6,
    "P0-3": 10   # 高上下文切换更重要
}
```
