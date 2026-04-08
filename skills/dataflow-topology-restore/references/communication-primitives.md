# NCCL/HCCL 通信原语识别方法

本文档描述如何从 Anansi Graph 中识别 NCCL/HCCL 通信模式和算法。

## NCCL 通信原语

### Ring All-Reduce

**识别特征**：
- 多个进程形成环形通信拓扑
- 每个进程与相邻两个进程通信
- 通信边形成闭环

**Anansi Graph 模式**：
```
Process 0 ← → Process 1 ← → Process 2 ← → Process 3 ←
     ↑                                              ↓
     └──────────────────────────────────────────────┘
```

**识别方法**：
```python
def identify_ring_allreduce(graph):
    # 1. 找到所有进程间通信边
    ipc_edges = [e for e in graph['edges'] if e['edge_type'] in ['SendToSocketEdge', 'IPCEdge']]
    
    # 2. 构建通信图
    comm_graph = build_communication_graph(ipc_edges)
    
    # 3. 检查是否形成环
    if is_ring_topology(comm_graph):
        return "Ring All-Reduce detected"
    return None
```

### Tree All-Reduce

**识别特征**：
- 存在一个根节点
- 其他节点与父节点通信
- 形成树状结构

**Anansi Graph 模式**：
```
        Root Process
           /    |    \
          /     |     \
     Child  Child  Child
```

### Hierarchical All-Reduce

**识别特征**：
- 多层级树状结构
- 节点按层级组织
- 跨层通信

---

## HCCL 通信原语

### H-D_R (Hierarchical-Ring) 算法

**识别特征**：
- 结合层级和环形拓扑
- 同层节点形成环
- 跨层节点形成树

**Anansi Graph 模式**：
```
Layer 0:  [NPU0] ← → [NPU1] ← → [NPU2] ← → [NPU3] ←
              ↑                    ↑
              |                    |
Layer 1:       [NPU4] ← → [NPU5]
```

**识别方法**：
```python
def identify_hierarchical_ring(graph):
    # 1. 按 NUMA 节点分组 NPU
    npu_numa_groups = group_npus_by_numa(graph)
    
    # 2. 检查每组内是否形成环
    for numa_id, npus in npu_numa_groups.items():
        if has_ring_topology(npus):
            print(f"NUMA {numa_id}: Ring topology detected")
    
    # 3. 检查跨组通信
    cross_numa_comm = analyze_cross_numa_communication(graph)
    return cross_numa_comm
```

---

## 通信带宽分析

### Socket 通信带宽

通过 `SendToSocketEdge` 的 `data_flow` 字段分析：

```python
def analyze_socket_bandwidth(socket_edge):
    data_flow = socket_edge.get('data_flow', {})
    
    total_bytes = data_flow.get('data_size', 0)
    total_packets = data_flow.get('packets_cnt', 0)
    duration = data_flow.get('end_time', 0) - data_flow.get('start_time', 0)
    
    if duration > 0:
        bandwidth_mbps = (total_bytes * 8) / (duration * 1e6)  # Mbps
        return {
            'total_bytes': total_bytes,
            'total_packets': total_packets,
            'bandwidth_mbps': bandwidth_mbps
        }
    return None
```

### NPU 间通信带宽估算

通过进程的内存访问模式估算：

```python
def estimate_npu_comm_bandwidth(graph, npu_id):
    # 找到访问该 NPU 的进程
    processes = find_processes_accessing_npu(graph, npu_id)
    
    total_bandwidth = 0
    for proc in processes:
        numa_access = get_numa_access_for_process(graph, proc)
        if numa_access:
            # 估算内存带宽
            mem_pages = numa_access['numa_affinity_info']['total_dirty_anon_pages']
            bandwidth = mem_pages * 4 * 1024  # 假设每页 4KB
            total_bandwidth += bandwidth
    
    return total_bandwidth
```

---

## 性能优化建议

### 1. 通信拓扑优化

- **Ring All-Reduce**：适合均匀通信负载
- **Tree All-Reduce**：适合非均匀通信负载
- **Hierarchical**：适合多 NUMA 节点场景

### 2. NUMA 亲和性优化

- 确保 Worker 进程运行在与 NPU 相同的 NUMA 节点
- 避免跨 NUMA 内存访问

### 3. 通信带宽优化

- 使用 RDMA 替代 Socket 通信
- 启用共享内存通信
