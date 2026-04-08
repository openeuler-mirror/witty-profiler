# NUMA 亲和性分析

本文档详细描述 NUMA 亲和性的分析方法和优化策略。

## 目录

1. [NUMA 架构基础](#numa-架构基础)
2. [NUMA 访问模式分析](#numa-访问模式分析)
3. [NUMA 亲和性评分](#numa-亲和性评分)
4. [NUMA 问题诊断](#numa-问题诊断)
5. [NUMA 优化策略](#numa-优化策略)

---

## NUMA 架构基础

### NUMA 拓扑结构

NUMA (Non-Uniform Memory Access) 架构中，每个处理器节点有自己的本地内存，访问本地内存比访问远端内存更快。

```
NUMA 拓扑示例:

        +-------------------+
        |   NUMA Node 0     |
        |  CPU: 0-23        |
        |  Memory: 64GB     |
        +-------------------+
               |
         (互连带宽: 200GB/s)
               |
        +-------------------+
        |   NUMA Node 1     |
        |  CPU: 24-47       |
        |  Memory: 64GB     |
        +-------------------+
```

### 访问延迟差异

| 访问类型 | 相对延迟 | 典型值 (ns) |
|---------|---------|------------|
| 本地内存访问 | 1x | 80-120 |
| 相邻 NUMA 访问 | 1.5-2x | 120-200 |
| 远端 NUMA 访问 | 2-3x | 200-300 |

### NUMA 距离矩阵

```python
# 示例: 4 NUMA 节点系统的距离矩阵
numa_distance_matrix = [
    #  0    1    2    3
    [  10,  21,  31,  21],  # NUMA 0
    [  21,  10,  21,  31],  # NUMA 1
    [  31,  21,  10,  21],  # NUMA 2
    [  21,  31,  21,  10]   # NUMA 3
]

# 距离解释:
# 10 = 本地访问 (基准值)
# 21 = 相邻 NUMA (2.1x 延迟)
# 31 = 远端 NUMA (3.1x 延迟)
```

---

## NUMA 访问模式分析

### 数据来源

NUMA 访问信息来自 witty-profiler 的 `NumaSniffer`，主要数据源：

1. **`/proc/[pid]/numa_maps`**: 内存页在 NUMA 节点的分布
2. **`/proc/[pid]/status`**: CPU 亲和性配置
3. **sched_monitor**: 线程在各 NUMA 节点的 CPU 运行时间

### 关键字段解析

#### NumaAccessInfo 结构

```python
class NumaAccessInfo:
    total_pages: Dict[int, int]           # 各 NUMA 节点的总页数
    read_only_pages: Dict[int, int]       # 各 NUMA 的只读页数
    dirty_anon_pages: Dict[int, int]      # 各 NUMA 的脏匿名页数
    proc_status: ProcStatus               # 进程状态信息
    numa_affinity_info: NumaAffinityInfo  # NUMA 亲和性信息
```

#### NumaAffinityInfo 结构

```python
class NumaAffinityInfo:
    cpu_runtime_pct_in_each_numa: List[float]  # 各 NUMA 的 CPU 时间占比
    mem_pages_in_each_numa: List[float]        # 各 NUMA 的内存页分布
```

### NUMA 访问模式分类

#### 1. 本地访问模式

**特征**:
- CPU 运行时间和内存访问集中在同一 NUMA 节点
- CPU-MEM 余弦相似度 > 0.8

**示例**:

```python
# CPU 运行时间分布
cpu_runtime_pct = [0.85, 0.10, 0.03, 0.02]

# 内存页分布
mem_pages_pct = [0.80, 0.12, 0.05, 0.03]

# 余弦相似度: 0.92 (优秀)
```

**性能**: 最优

---

#### 2. 跨 NUMA 访问模式

**特征**:
- CPU 运行在一个 NUMA，但访问另一个 NUMA 的内存
- CPU-MEM 余弦相似度 < 0.5

**示例**:

```python
# CPU 运行时间分布 (主要在 NUMA 0)
cpu_runtime_pct = [0.75, 0.15, 0.05, 0.05]

# 内存页分布 (主要在 NUMA 2)
mem_pages_pct = [0.10, 0.15, 0.60, 0.15]

# 余弦相似度: 0.38 (警告)
```

**性能**: 中等延迟，需要优化

---

#### 3. 混合访问模式

**特征**:
- CPU 和内存分布在多个 NUMA 节点
- CPU-MEM 余弦相似度 0.5-0.8

**示例**:

```python
# CPU 运行时间分布
cpu_runtime_pct = [0.40, 0.35, 0.15, 0.10]

# 内存页分布
mem_pages_pct = [0.35, 0.40, 0.15, 0.10]

# 余弦相似度: 0.75 (良好)
```

**性能**: 可接受，但可以优化

---

#### 4. 远端访问模式

**特征**:
- 主要访问远端 NUMA 内存
- CPU-MEM 余弦相似度 < 0.3

**示例**:

```python
# CPU 运行时间分布 (主要在 NUMA 0)
cpu_runtime_pct = [0.80, 0.10, 0.05, 0.05]

# 内存页分布 (主要在 NUMA 3)
mem_pages_pct = [0.05, 0.10, 0.15, 0.70]

# 余弦相似度: 0.22 (严重)
```

**性能**: 严重性能下降，需要紧急优化

---

## NUMA 亲和性评分

### 余弦相似度计算

```python
import numpy as np

def calculate_cosine_similarity(cpu_dist, mem_dist):
    """
    计算 CPU 和内存分布的余弦相似度
    
    Args:
        cpu_dist: 各 NUMA 的 CPU 时间占比列表
        mem_dist: 各 NUMA 的内存页占比列表
    
    Returns:
        相似度值 [0, 1]，越接近 1 表示亲和性越好
    """
    cpu_vec = np.array(cpu_dist)
    mem_vec = np.array(mem_dist)
    
    dot_product = np.dot(cpu_vec, mem_vec)
    cpu_norm = np.linalg.norm(cpu_vec)
    mem_norm = np.linalg.norm(mem_vec)
    
    if cpu_norm == 0 or mem_norm == 0:
        return 0.0
    
    return dot_product / (cpu_norm * mem_norm)
```

### 评分标准

| 相似度范围 | 评分等级 | 性能影响 | 建议 |
|-----------|---------|---------|------|
| > 0.8 | 优秀 | 最优 | 保持现状 |
| 0.6-0.8 | 良好 | 轻微影响 | 可优化 |
| 0.4-0.6 | 一般 | 中等影响 | 建议优化 |
| 0.2-0.4 | 警告 | 显著影响 | 需要优化 |
| < 0.2 | 严重 | 严重影响 | 紧急优化 |

### 综合评分算法

```python
def calculate_numa_affinity_score(thread):
    """
    计算 NUMA 亲和性综合评分
    
    Returns:
        {
            "score": float,          # 综合评分 [0, 100]
            "grade": str,            # 等级
            "cpu_mem_similarity": float,
            "remote_access_ratio": float,
            "dominant_numa": int,
            "issues": List[str]
        }
    """
    info = thread.get("numa_access_info", {})
    affinity_info = info.get("numa_affinity_info", {})
    
    cpu_dist = affinity_info.get("cpu_runtime_pct_in_each_numa", [])
    mem_dist = affinity_info.get("mem_pages_in_each_numa", [])
    
    if not cpu_dist or not mem_dist:
        return {
            "score": 0,
            "grade": "未知",
            "issues": ["缺少 NUMA 访问数据"]
        }
    
    # 计算余弦相似度
    similarity = calculate_cosine_similarity(cpu_dist, mem_dist)
    
    # 计算远端访问比例
    remote_ratio = calculate_remote_access_ratio(cpu_dist, mem_dist)
    
    # 找出主导 NUMA 节点
    dominant_cpu_numa = np.argmax(cpu_dist)
    dominant_mem_numa = np.argmax(mem_dist)
    
    # 计算综合评分
    score = similarity * 100
    
    # 识别问题
    issues = []
    if similarity < 0.5:
        issues.append(f"CPU-MEM 分布不一致 (相似度: {similarity:.2f})")
    if dominant_cpu_numa != dominant_mem_numa:
        issues.append(f"CPU 主导 NUMA ({dominant_cpu_numa}) != 内存主导 NUMA ({dominant_mem_numa})")
    if remote_ratio > 0.3:
        issues.append(f"高远端访问比例 ({remote_ratio*100:.1f}%)")
    
    # 确定等级
    if score >= 80:
        grade = "优秀"
    elif score >= 60:
        grade = "良好"
    elif score >= 40:
        grade = "一般"
    elif score >= 20:
        grade = "警告"
    else:
        grade = "严重"
    
    return {
        "score": score,
        "grade": grade,
        "cpu_mem_similarity": similarity,
        "remote_access_ratio": remote_ratio,
        "dominant_cpu_numa": dominant_cpu_numa,
        "dominant_mem_numa": dominant_mem_numa,
        "issues": issues
    }
```

---

## NUMA 问题诊断

### 诊断流程

```python
def diagnose_numa_issues(thread):
    """
    诊断 NUMA 相关问题
    
    Returns:
        {
            "has_issue": bool,
            "severity": str,
            "issue_type": str,
            "root_cause": str,
            "recommendations": List[str]
        }
    """
    score_result = calculate_numa_affinity_score(thread)
    
    if score_result["score"] >= 60:
        return {
            "has_issue": False,
            "severity": "无",
            "issue_type": "无",
            "root_cause": "",
            "recommendations": []
        }
    
    # 分析问题类型
    issues = score_result["issues"]
    
    if "CPU 主导 NUMA" in str(issues):
        issue_type = "CPU-MEM NUMA 不匹配"
        root_cause = f"线程主要运行在 NUMA {score_result['dominant_cpu_numa']}，但内存主要在 NUMA {score_result['dominant_mem_numa']}"
        recommendations = [
            f"使用 numactl --cpunodebind={score_result['dominant_mem_numa']} --membind={score_result['dominant_mem_numa']} 重新启动进程",
            "或使用 numactl --preferred 重新分配内存"
        ]
    
    elif score_result["remote_access_ratio"] > 0.3:
        issue_type = "高远端访问"
        root_cause = f"远端 NUMA 访问比例高达 {score_result['remote_access_ratio']*100:.1f}%"
        recommendations = [
            "调整 NUMA 亲和性，将线程和内存绑定到同一 NUMA",
            "考虑数据分区，减少跨 NUMA 访问"
        ]
    
    else:
        issue_type = "NUMA 访问分散"
        root_cause = "CPU 和内存分布在多个 NUMA 节点"
        recommendations = [
            "检查是否有不必要的内存迁移",
            "考虑使用 NUMA 感知的数据结构"
        ]
    
    # 确定严重程度
    if score_result["score"] < 20:
        severity = "严重"
    elif score_result["score"] < 40:
        severity = "警告"
    else:
        severity = "一般"
    
    return {
        "has_issue": True,
        "severity": severity,
        "issue_type": issue_type,
        "root_cause": root_cause,
        "recommendations": recommendations
    }
```

---

## NUMA 优化策略

### 策略 1: NUMA 亲和性绑定

**适用场景**: CPU-MEM NUMA 不匹配

**实施方法**:

```bash
# 方法 1: 使用 numactl 绑定
numactl --cpunodebind=0 --membind=0 python train.py

# 方法 2: 使用 preferred (允许溢出)
numactl --cpunodebind=0 --preferred=0 python train.py

# 方法 3: 使用 interleave (交错分配)
numactl --interleave=all python train.py
```

**效果评估**:
- 本地访问比例提升 20-40%
- 内存访问延迟降低 30-50%

---

### 策略 2: 数据分区

**适用场景**: 高远端访问

**实施方法**:

```python
# 将数据按 NUMA 节点分区
def partition_data_by_numa(data, num_numa_nodes):
    partitions = []
    chunk_size = len(data) // num_numa_nodes
    
    for i in range(num_numa_nodes):
        start = i * chunk_size
        end = start + chunk_size if i < num_numa_nodes - 1 else len(data)
        partitions.append(data[start:end])
    
    return partitions

# 每个 worker 处理本地 NUMA 的数据
def worker_local(worker_id, data_partition):
    # 绑定到特定 NUMA
    os.sched_setaffinity(0, get_numa_cpus(worker_id))
    
    # 处理本地数据
    process(data_partition)
```

**效果评估**:
- 远端访问降低 50-70%
- 整体吞吐量提升 15-30%

---

### 策略 3: NUMA 感知的数据结构

**适用场景**: NUMA 访问分散

**实施方法**:

```python
# 使用 NUMA 感知的内存分配器
import numa

class NumaAwareArray:
    def __init__(self, size, numa_node):
        self.numa_node = numa_node
        self.data = numa.alloc_onnode(size * 8, numa_node)
    
    def __getitem__(self, index):
        return self.data[index]
    
    def __setitem__(self, index, value):
        self.data[index] = value
```

**效果评估**:
- 内存访问延迟降低 20-40%
- 缓存命中率提升 10-20%

---

### 策略 4: 内存迁移

**适用场景**: 已有进程的 NUMA 优化

**实施方法**:

```bash
# 使用 migratepages 迁移内存
migratepages <pid> <from_node> <to_node>

# 示例: 将进程 12345 的内存从 NUMA 0 迁移到 NUMA 1
migratepages 12345 0 1
```

**效果评估**:
- 立即生效，无需重启进程
- 可能导致短暂的性能波动

---

## NUMA 监控指标

### 关键监控指标

| 指标名称 | 数据来源 | 监控频率 | 告警阈值 |
|---------|---------|---------|---------|
| CPU-MEM 相似度 | numa_access_info | 10s | < 0.5 |
| 远端访问比例 | numa_maps | 10s | > 30% |
| NUMA 互连带宽 | 系统监控 | 1s | > 80% |
| 本地访问比例 | numa_access_info | 10s | < 70% |

### 监控脚本示例

```python
def monitor_numa_affinity(pid, interval=10):
    """
    持续监控进程的 NUMA 亲和性
    """
    while True:
        numa_info = get_numa_access_info(pid)
        score = calculate_numa_affinity_score({"numa_access_info": numa_info})
        
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"NUMA 亲和性: {score['score']:.1f} ({score['grade']})")
        
        if score["issues"]:
            print(f"  问题: {', '.join(score['issues'])}")
        
        time.sleep(interval)
```

---

## 最佳实践

### 1. 进程启动时绑定

```bash
# 推荐: 启动时明确绑定
numactl --cpunodebind=0 --membind=0 python train.py

# 不推荐: 依赖系统默认调度
python train.py
```

### 2. 多进程场景

```python
# 每个 worker 绑定到不同的 NUMA
for worker_id in range(num_workers):
    numa_node = worker_id % num_numa_nodes
    cmd = f"numactl --cpunodebind={numa_node} --membind={numa_node} python worker.py --id {worker_id}"
    subprocess.Popen(cmd, shell=True)
```

### 3. 容器场景

```bash
# Docker 容器 NUMA 绑定
docker run --cpuset-cpus=0-23 --memory=64g --memory-numa-node=0 myimage
```

### 4. AI 框架集成

```python
# PyTorch NUMA 感知
import torch

# 设置线程亲和性
torch.set_num_threads(24)
os.sched_setaffinity(0, range(0, 24))  # 绑定到 NUMA 0 的 CPU
```
