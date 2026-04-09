# NUMA 架构与跨节点访问识别

本文档描述 NUMA 架构以及如何从 Anansi Graph 中识别跨 NUMA 访问问题。

## NUMA 架构基础

### 什么是 NUMA？

NUMA (Non-Uniform Memory Access) 是一种多处理器内存架构，每个处理器访问本地内存比访问远程内存更快。

### NUMA 拓扑结构

```
┌─────────────────────────────────────────────────────────────┐
│                        NUMA Node 0                              │
│  CPU: 0-23         Memory: Local (Fast)                        │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         │ Distance: 10      │ Distance: 24     │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                        NUMA Node 1                              │
│  CPU: 24-47        Memory: Remote (Slower)                       │
└─────────────────────────────────────────────────────────────┘
```

### NUMA 距离矩阵

通过 `NumaEntity.distance_to_all_numa` 字段获取：

| 距离值 | 含义 |
|-------|------|
| 10 | 本地访问 (最快) |
| 11- 相邻节点访问 |
| 24 | 跨 Socket 访问 |
| 25+ 远程节点访问 |
| 32 | 最远节点访问 |

---

## Anansi NUMA 相关实体

### NumaEntity

```json
{
  "entity_type": "NumaEntity",
  "numa_id": 0,
  "cpu_set": "0-23",
  "memory_set": "0-1,130-255",
  "numa_stats": {
    "numa_hit": 664496298,
    "numa_miss": 4016745,
    "numa_foreign": 0,
    "interleave_hit": 2601,
    "local_node": 652692921,
    "other_node": 15820122
  },
  "distance_to_all_numa": {
    "0": 10,
    "1": 11,
    "2": 24,
    "3": 25
  }
}
```

### NumaSetEntity

NUMA 节点集合，用于表示进程可访问的多个 NUMA 节点。

```json
{
  "entity_type": "NumaSetEntity",
  "numa_id_str": "0,22-4,6"
}
```

---

## 跨 NUMA 访问识别

### NumaAccessEdge 分析

`NumaAccessEdge` 包含详细的 NUMA 访问信息

```json
{
  "edge_type": "NumaAccessEdge",
  "source_node": { "entity_type": "ProcessEntity", "pid": 1894856 },
  "target_node": { "entity_type": "NumaSetEntity", "numa_id_str": "0,2-4,6" },
  "numa_access_info": {
    "proc_status": {
      "cpus_allowed_list": "72-95",
      "mems_allowed_list": "0-7"
    },
    "numa_affinity_info": {
      "cpu_runtime_pct_in_each_numa": [0, 0, 0, 1.0, 0, 0, 0, 0],
      "mem_pages_in_each_numa": [3, 0, 1, 244409, 1, 1540, 0, 0],
      "cpu_mem_access_cosine_similarity": 0.9937183375753189
    }
  }
}
```

### 关键指标解读

#### cpu_runtime_pct_in_each_numa

CPU 在各 NUMA 节点的运行时间分布

- 值为 1.0 表示 100% 时间在该 NUMA
- 值为 0.0 表示未在该 NUMA 运行

#### mem_pages_in_each_numa

进程在各 NUMA 节点的内存页分布

#### cpu_mem_access_cosine_similarity

CPU-内存访问一致性分数

- **> 0.8**: 良好的 NUMA 亲和性
- **< 0.5**: 存在严重的跨 NUMA 访问

---

## 跨 NUMA 访问检测方法

```python
def detect_cross_numa_access(numa_access_edge):
    info = numa_access_edge.get('numa_access_info', {})
    affinity = info.get('numa_affinity_info', {})
    
    similarity = affinity.get('cpu_mem_access_cosine_similarity', 0)
    
    # 获取 CPU 主要运行的 NUMA
    cpu_dist = affinity.get('cpu_runtime_pct_in_each_numa', [])
    primary_numa = cpu_dist.index(max(cpu_dist)) if max(cpu_dist) > 0.5 else None
    
    # 获取内存主要分布的 NUMA
    mem_dist = affinity.get('mem_pages_in_each_numa', [])
    primary_mem_numa = mem_dist.index(max(mem_dist)) if max(mem_dist) > 005 else None
    
    # 检查是否一致
    if primary_numa is not None and primary_mem_numa is not None:
        if primary_numa != primary_mem_numa:
            return {
                'status': 'CROSS_NUMA',
                'cpu_numa': primary_numa,
                'mem_numa': primary_mem_numa,
                'similarity': similarity
            }
    
    return {
        'status': 'OK',
        'cpu_numa': primary_numa,
        'mem_numa': primary_mem_numa,
        'similarity': similarity
    }
```

---

## 性能影响分析

### 跨 NUMA 访问延迟

| 访问类型 | 相对延迟倍数 |
|---------|--------------|
| 本地访问 | 1x |
| 相邻节点 | 1.1-1.5x |
| 跨 Socket | 2-4x |
| 远程节点 | 5-10x |

### 对 AI 训练的影响

1. **梯度同步延迟**：跨 NUMA 访问增加 All-Reduce 同步时间
2. **内存带宽下降**：远程内存访问降低有效带宽
3. **缓存命中率下降**：跨 NUMA 访问影响 CPU 缓存效率

---

## 优化建议

### 1. 进程绑定

将进程绑定到与访问数据最近的 NUMA 节点

```bash
# 使用 numactl 绑定进程
numactl --cpunodebind=0 <pid>
```

### 2. 内存分配

使用本地内存分配策略

```python
import numa
# 在特定 NUMA 节点分配内存
numa.set_preferred(0)  # NUMA node 0
```

### 3. NPU 亲和性

确保 NPU 与进程在同一 NUMA 节点

```python
# 检查 NPU 的 NUMA 亲和性
npu_numa = get_npu_numa_affinity(npu_id)
process_numa = get_process_numa_affinity(pid)
if npu_numa != process_numa:
    # 需要调整进程绑定
```
