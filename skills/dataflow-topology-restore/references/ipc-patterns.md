# 进程间通信模式分析

本文档描述如何从 Anansi Graph 中识别和分析进程间通信 (IPC) 模式。

## IPC 类型概述

### 1. Socket 通信

**识别方法**：
- `SocketEntity` 实体
- `BelongEdge` (Socket → Thread/Process)
- `SendToSocketEdge` (Process/Thread → Socket)

**数据流模式**：
```
Process A → SendToSocketEdge → Socket ← BelongEdge ← Thread B
```

**分析代码**：
```python
def analyze_socket_communication(graph):
    sockets = get_entities_by_type(graph, 'SocketEntity')
    socket_edges = get_edges_by_type(graph, 'SendToSocketEdge')
    
    communications = []
    for edge in socket_edges:
        source = edge['source_node']
        target = edge['target_node']
        
        # 获取数据流统计
        data_flow = edge.get('data_flow', {})
        
        communications.append({
            'source_pid': source.get('pid'),
            'target_socket': f"{target.get('socket_addr')}:{target.get('socket_port')}",
            'bytes': data_flow.get('data_size', 0),
            'packets': data_flow.get('packets_cnt', 0)
        })
    
    return communications
```

---

### 2. 共享内存通信

**识别方法**：
- `SharedMemoryEntity` 实体
- `AccessEdge` (Process → SharedMemory)

**数据流模式**：
```
Process A → AccessEdge → SharedMemory ← AccessEdge ← Process B
```

**分析代码**：
```python
def analyze_shared_memory_communication(graph):
    shm_entities = get_entities_by_type(graph, 'SharedMemoryEntity')
    access_edges = get_edges_by_type(graph, 'AccessEdge')
    
    shm_access = {}
    for edge in access_edges:
        target = edge['target_node']
        if target.get('entity_type') == 'SharedMemoryEntity':
            shm_name = target.get('shm_name')
            source_pid = edge['source_node'].get('pid')
            
            if shm_name not in shm_access:
                shm_access[shm_name] = []
            shm_access[shm_name].append(source_pid)
    
    # 找到多进程共享的内存
    multi_process_shm = {
        name: name for name, pids in shm_access.items() 
        if len(pids) > 1
    }
    
    return multi_process_shm
```

---

### 3. 管道通信

**识别方法**：
- `PipeInodeEntity` 实体
- `IPCEdge` (Process → Process)

**数据流模式**：
```
Process A → IPCEdge → PipeInodeEntity ← IPCEdge ← Process B
```

---

### 4. Unix Domain Socket

**识别方法**：
- `SocketEntity` with `socket_type = "UNIX"`
- `BelongEdge` 和 `SendToSocketEdge`

**特点**：
- 本地进程间通信
- 比 TCP 更低的延迟
- 不经过网络栈

---

### 5. RDMA 通信

**识别方法**：
- `RdmaQueuePairEndpoint` 实体
- `ConnectToEdge` (QP → QP)
- `RdmaProtectionDomain` 和 `RdmaMemoryRegion`

**数据流模式**：
```
Process A → RdmaLocalQP → ConnectToEdge → RdmaRemoteQP ← Process B
```

**分析代码**：
```python
def analyze_rdma_communication(graph):
    qps = get_entities_by_type(graph, 'RdmaQueuePairEndpoint')
    connect_edges = get_edges_by_type(graph, 'ConnectToEdge')
    
    rdma_connections = []
    for edge in connect_edges:
        source = edge['source_node']
        target = edge['target_node']
        
        if 'RdmaQueuePairEndpoint' in str(source) and 'RdmaQueuePairEndpoint' in str(target):
            rdma_connections.append({
                'local_qp': source.get('qpn'),
                'remote_qp': target.get('qpn')
            })
    
    return rdma_connections
```

---

## IPC 性能分析

### 延迟对比

| IPC 类型 | 典型延迟 | 适用场景 |
|---------|---------|---------|
| 共享内存 | 最低 (纳秒级) | 高吞吐量数据交换 |
| Unix Domain Socket | 低 (微秒级) | 本地进程间通信 |
| TCP Socket | 中等 (毫秒级) | 跨节点通信 |
| RDMA | 低 (微秒级) | 高性能计算 |
| 管道 | 中等 | 篱式进程通信 |

### 带宽分析

```python
def estimate_ipc_bandwidth(graph, ipc_type):
    if ipc_type == 'socket':
        edges = get_edges_by_type(graph, 'SendToSocketEdge')
        total_bytes = sum(e.get('data_flow', {}).get('data_size', 0) for e in edges)
    elif ipc_type == 'shared_memory':
        entities = get_entities_by_type(graph, 'SharedMemoryEntity')
        total_bytes = sum(e.get('shm_size', 0) for e in entities)
    else:
        return 0
    
    return total_bytes
```

---

## 优化建议

### 1. 高吞吐量场景
- 优先使用共享内存
- 考虑 RDMA 替代 Socket

### 2. 跨节点场景
- 使用 RDMA 降低延迟
- 优化 Socket 缓冲区大小

### 3. 多进程协作场景
- 使用 Unix Domain Socket
- 合理设置共享内存大小
