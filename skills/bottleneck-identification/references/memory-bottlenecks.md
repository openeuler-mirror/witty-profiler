# 内存层次瓶颈

本文档详细描述内存层次瓶颈的识别方法，包括 Cache Miss、HBM 带宽墙等问题。

## 目录

1. [内存层次结构](#内存层次结构)
2. [内存瓶颈类型](#内存瓶颈类型)
3. [识别方法](#识别方法)
4. [优化策略](#优化策略)

---

## 内存层次结构

### 典型内存层次

```
┌─────────────────────────────────────┐
│  CPU Registers                      │  延迟: ~1 cycle
│  容量: KB 级别                       │
├─────────────────────────────────────┤
│  L1 Cache (指令 + 数据)              │  延迟: ~4 cycles
│  容量: 32-64 KB per core             │
├─────────────────────────────────────┤
│  L2 Cache                           │  延迟: ~12 cycles
│  容量: 256 KB - 1 MB per core        │
├─────────────────────────────────────┤
│  L3 Cache (LLC)                     │  延迟: ~40 cycles
│  容量: 8-64 MB shared                │
├─────────────────────────────────────┤
│  Main Memory (DDR/HBM)              │  延迟: ~100-200 cycles
│  容量: GB - TB 级别                  │
├─────────────────────────────────────┤
│  Storage (SSD/HDD)                  │  延迟: ~10^5-10^6 cycles
│  容量: TB - PB 级别                  │
└─────────────────────────────────────┘
```

### 内存性能指标

| 层次 | 带宽 | 延迟 | 容量 |
|-----|------|------|------|
| L1 Cache | ~1 TB/s | ~1 ns | 32-64 KB |
| L2 Cache | ~500 GB/s | ~4 ns | 256 KB - 1 MB |
| L3 Cache | ~200 GB/s | ~12 ns | 8-64 MB |
| DDR4 | ~50 GB/s | ~80 ns | 16-256 GB |
| DDR5 | ~100 GB/s | ~70 ns | 32-512 GB |
| HBM2 | ~300 GB/s | ~100 ns | 8-24 GB |
| HBM3 | ~800 GB/s | ~90 ns | 16-64 GB |

---

## 内存瓶颈类型

### 1. Cache Miss Storm (缓存缺失风暴)

#### 定义
缓存缺失率过高，导致大量内存访问，性能严重下降。

#### 识别特征

**指标阈值**:
- L1 缓存命中率 < 80%
- L2 缓存命中率 < 70%
- LLC 缓存命中率 < 60%

**数据来源**:
- `cache_monitor` 数据
- `CacheMonitorColumn.LLC` 字段
- perf 事件

#### 严重性判定

```python
def assess_cache_miss_severity(l1_miss_rate, llc_miss_rate):
    if llc_miss_rate > 40:
        return "Critical"
    elif llc_miss_rate > 30:
        return "Warning"
    elif llc_miss_rate > 20:
        return "Notice"
    else:
        return "Info"
```

#### 根因分析

| 缓存缺失类型 | 根因 | 特征 |
|------------|------|------|
| **容量缺失** | 工作集超过缓存容量 | 增加 cache 大小可改善 |
| **冲突缺失** | 地址映射冲突 | 改变数据布局可改善 |
| **强制缺失** | 首次访问 | 无法避免 |
| **无效缺失** | 缓存一致性协议 | 多线程共享数据 |

#### 优化建议

1. **优化数据局部性**
   ```python
   # 优化前: 访存模式不友好
   for i in range(N):
       for j in range(M):
           sum += matrix[i][j]  # 行优先访问
   
   # 优化后: 访存模式友好
   for j in range(M):
       for i in range(N):
           sum += matrix[i][j]  # 列优先访问（如果矩阵是列优先存储）
   ```

2. **数据分块**
   ```python
   # 分块处理提高缓存命中率
   BLOCK_SIZE = 64
   for i in range(0, N, BLOCK_SIZE):
       for j in range(0, M, BLOCK_SIZE):
           # 处理块内数据
           for ii in range(i, min(i+BLOCK_SIZE, N)):
               for jj in range(j, min(j+BLOCK_SIZE, M)):
                   process(matrix[ii][jj])
   ```

3. **预取**
   ```c
   // 软件预取
   __builtin_prefetch(&matrix[i+8][j], 0, 3);
   ```

---

### 2. Memory Bandwidth Wall (内存带宽墙)

#### 定义
内存带宽饱和，成为性能瓶颈。

#### 识别特征

**指标阈值**:
- 内存带宽利用率 > 80%
- 内存带宽 > 理论带宽 70%
- 多个进程竞争内存带宽

**数据来源**:
- PCM (Performance Counter Monitor)
- 内存控制器计数器
- 系统监控工具

#### 严重性判定

```python
def assess_memory_bandwidth_severity(bandwidth_usage):
    if bandwidth_usage > 90:
        return "Critical"
    elif bandwidth_usage > 80:
        return "Warning"
    elif bandwidth_usage > 70:
        return "Notice"
    else:
        return "Info"
```

#### 根因分析

| 根因 | 特征 | 解决方案 |
|-----|------|---------|
| **数据访问密集** | 算术强度低 | 优化算法减少访存 |
| **多进程竞争** | 多进程内存带宽高 | 错峰访问或限制带宽 |
| **内存通道不均衡** | 部分通道过载 | 优化内存分配 |
| **NUMA 不均衡** | 部分 NUMA 过载 | NUMA 感知分配 |

#### 优化建议

1. **提高算术强度**
   ```python
   # 优化前: 算术强度低
   for i in range(N):
       c[i] = a[i] + b[i]  # 1 FLOP / 12 Bytes = 0.083 FLOP/Byte
   
   # 优化后: 算术强度高
   for i in range(N):
       c[i] = a[i] * b[i] + a[i] * c[i]  # 3 FLOPs / 12 Bytes = 0.25 FLOP/Byte
   ```

2. **使用缓存**
   - 增加缓存命中率
   - 减少内存访问次数

3. **数据压缩**
   - 减少数据传输量
   - 使用压缩格式

---

### 3. HBM Bandwidth Limit (HBM 带宽限制)

#### 定义
HBM (High Bandwidth Memory) 带宽成为 NPU/GPU 性能瓶颈。

#### 识别特征

**指标阈值**:
- HBM 带宽利用率 > 80%
- NPU/GPU 利用率低
- 内存延迟高

**数据来源**:
- NPU/GPU 驱动统计
- 性能计数器
- 应用监控

#### 严重性判定

```python
def assess_hbm_bandwidth_severity(bandwidth_usage, npu_utilization):
    if bandwidth_usage > 90 and npu_utilization < 50:
        return "Critical"
    elif bandwidth_usage > 80 and npu_utilization < 70:
        return "Warning"
    else:
        return "Notice"
```

#### 优化建议

1. **优化内存访问模式**
   - 合并内存访问
   - 使用共享内存
   - 优化内存对齐

2. **减少内存访问**
   - 使用缓存
   - 数据复用
   - 算子融合

3. **使用更高带宽的 HBM**
   - HBM3 > HBM2e > HBM2
   - 增加堆叠层数

---

### 4. Memory Latency Bottleneck (内存延迟瓶颈)

#### 定义
内存访问延迟高，影响系统响应。

#### 识别特征

**指标阈值**:
- 内存延迟 > 150ns
- 内存延迟 > 正常值 2 倍
- 高延迟内存访问比例高

**数据来源**:
- 内存延迟测试工具
- PCM 延迟统计
- 应用性能分析

#### 严重性判定

```python
def assess_memory_latency_severity(latency_ns):
    if latency_ns > 200:
        return "Critical"
    elif latency_ns > 150:
        return "Warning"
    elif latency_ns > 120:
        return "Notice"
    else:
        return "Info"
```

#### 根因分析

| 根因 | 特征 | 解决方案 |
|-----|------|---------|
| **NUMA 远端访问** | 跨 NUMA 访问多 | NUMA 亲和性优化 |
| **内存控制器拥塞** | 控制器队列深 | 减少并发访问 |
| **TLB 缺失** | TLB 缺失率高 | 大页内存 |
| **内存碎片** | 分配延迟高 | 内存池 |

#### 优化建议

1. **使用大页内存**
   ```bash
   # 配置大页
   echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
   
   # 应用使用大页
   export HUGETLB_MORECORE=yes
   ```

2. **NUMA 优化**
   ```bash
   # 绑定到本地 NUMA
   numactl --cpunodebind=0 --membind=0 ./app
   ```

3. **内存池**
   ```cpp
   // 使用内存池减少分配延迟
   MemoryPool pool(1024 * 1024);  // 1 MB pool
   void* ptr = pool.allocate(1024);  // 快速分配
   ```

---

### 5. Memory Capacity Bottleneck (内存容量瓶颈)

#### 定义
内存容量不足，导致频繁换页或 OOM。

#### 识别特征

**指标阈值**:
- 内存使用率 > 90%
- 换页频繁
- OOM Killer 触发

**数据来源**:
- /proc/meminfo
- vmstat
- 应用监控

#### 严重性判定

```python
def assess_memory_capacity_severity(usage_ratio, swap_rate):
    if usage_ratio > 95 or swap_rate > 100:
        return "Critical"
    elif usage_ratio > 90 or swap_rate > 10:
        return "Warning"
    elif usage_ratio > 85:
        return "Notice"
    else:
        return "Info"
```

#### 优化建议

1. **减少内存占用**
   - 优化数据结构
   - 使用内存映射文件
   - 数据压缩

2. **增加内存**
   - 扩展物理内存
   - 使用 swap（性能下降）

3. **内存限制**
   ```bash
   # 限制进程内存使用
   ulimit -v 8388608  # 8 GB
   ```

---

## 识别方法

### 基于 cache_monitor 数据

```python
def identify_cache_bottlenecks(cache_data):
    """
    从 cache_monitor 数据识别缓存瓶颈
    """
    bottlenecks = []
    
    # 计算缓存缺失率
    total_access = cache_data['total'].sum()
    l1i_miss = cache_data['l1i'].sum()
    llc_miss = cache_data['llc'].sum()
    
    l1i_miss_rate = l1i_miss / total_access if total_access > 0 else 0
    llc_miss_rate = llc_miss / total_access if total_access > 0 else 0
    
    # 判定瓶颈
    if llc_miss_rate > 0.4:
        bottlenecks.append({
            "type": "Cache Miss Storm",
            "severity": "Critical",
            "llc_miss_rate": llc_miss_rate
        })
    
    return bottlenecks
```

### 基于 NUMA 访问数据

```python
def identify_numa_memory_bottlenecks(numa_data):
    """
    从 NUMA 访问数据识别内存瓶颈
    """
    bottlenecks = []
    
    # 分析 NUMA 访问模式
    for pid, numa_info in numa_data.items():
        remote_ratio = calculate_remote_access_ratio(numa_info)
        
        if remote_ratio > 0.3:
            bottlenecks.append({
                "type": "Cross-NUMA Memory Access",
                "severity": assess_severity(remote_ratio),
                "pid": pid,
                "remote_ratio": remote_ratio
            })
    
    return bottlenecks
```

---

## 优化策略

### 通用优化原则

1. **提高局部性**
   - 时间局部性: 重用近期访问的数据
   - 空间局部性: 访问相邻数据

2. **减少访存次数**
   - 数据复用
   - 算子融合
   - 缓存优化

3. **优化访存模式**
   - 顺序访问
   - 对齐访问
   - 合并访问

4. **使用高效内存**
   - HBM 替代 DDR
   - 大页内存
   - NUMA 感知分配

### 性能监控

持续监控内存性能指标：

```python
def monitor_memory_performance(interval=10):
    while True:
        # 收集内存指标
        cache_stats = collect_cache_stats()
        bandwidth_stats = collect_bandwidth_stats()
        numa_stats = collect_numa_stats()
        
        # 检测瓶颈
        bottlenecks = detect_memory_bottlenecks(
            cache_stats, bandwidth_stats, numa_stats
        )
        
        # 告警
        if bottlenecks:
            alert_bottlenecks(bottlenecks)
        
        time.sleep(interval)
```
