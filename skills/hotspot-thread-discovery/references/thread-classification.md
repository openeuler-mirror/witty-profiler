# 线程分类学

本文档详细描述 AI 训练系统中线程的分类方法，帮助识别和分析不同类型线程的性能特征。

## 目录

1. [分类原则](#分类原则)
2. [线程类型详解](#线程类型详解)
3. [分类方法](#分类方法)
4. [混合型线程处理](#混合型线程处理)

---

## 分类原则

线程分类基于以下维度：

1. **CPU 使用模式**：CPU 使用率、用户态/内核态比例
2. **I/O 行为**：网络 I/O、磁盘 I/O、设备 I/O
3. **同步行为**：锁等待、条件变量、屏障
4. **内存访问模式**：NUMA 访问、缓存行为
5. **命名模式**：线程名称中的关键词

---

## 线程类型详解

### 1. 计算线程 (Compute Thread)

#### 定义
执行核心计算任务的线程，通常是 AI 模型的前向/反向传播计算。

#### 特征

| 特征维度 | 典型值 | 判定标准 |
|---------|-------|---------|
| CPU 使用率 | 高 (>70%) | 持续高 CPU 使用 |
| 用户态比例 | 高 (>80%) | 大部分时间在用户态计算 |
| 上下文切换 | 低 (<100/s) | 很少主动让出 CPU |
| I/O 等待 | 低 (<5%) | 很少等待 I/O |
| 缓存缺失 | 中等 | 取决于数据局部性 |

#### 典型名称模式

```
worker
compute
forward
backward
matmul
conv
gemm
```

#### 性能关注点

1. **CPU 亲和性**：是否绑定到特定 CPU 核心
2. **缓存友好性**：数据访问是否缓存友好
3. **SIMD 利用率**：是否充分利用向量指令
4. **内存带宽**：是否受内存带宽限制

#### 优化方向

- 优化算法减少计算量
- 改进数据局部性提高缓存命中率
- 使用 SIMD 指令加速
- 绑定 CPU 核心减少迁移

---

### 2. 通信线程 (Communication Thread)

#### 定义
负责进程间或节点间通信的线程，处理数据传输和同步。

#### 特征

| 特征维度 | 典型值 | 判定标准 |
|---------|-------|---------|
| CPU 使用率 | 中等 (20-50%) | 处理通信协议 |
| 内核态比例 | 中等 (30-50%) | 系统调用较多 |
| 上下文切换 | 中等 (100-1000/s) | 等待网络 I/O |
| I/O 等待 | 中等 (10-30%) | 等待网络传输 |
| Socket 活动 | 高 | 大量网络通信 |

#### 典型名称模式

```
nccl
hccl
comm
send
recv
network
socket
rdma
```

#### 性能关注点

1. **网络带宽利用率**：是否充分利用网络带宽
2. **跨 NUMA 访问**：通信缓冲区的 NUMA 位置
3. **协议开销**：通信协议的处理开销
4. **延迟**：通信延迟对整体性能的影响

#### 优化方向

- 使用 RDMA 减少协议开销
- 调整通信缓冲区大小
- 优化跨 NUMA 通信路径
- 使用通信计算重叠

---

### 3. 驱动线程 (Driver Thread)

#### 定义
管理与硬件设备交互的线程，如 GPU/NPU 驱动线程。

#### 特征

| 特征维度 | 典型值 | 判定标准 |
|---------|-------|---------|
| CPU 使用率 | 低 (<20%) | 等待设备完成 |
| 内核态比例 | 高 (>50%) | 设备驱动调用 |
| 上下文切换 | 中等 | 等待设备中断 |
| 设备等待 | 高 | 大部分时间等待设备 |
| 中断处理 | 高 | 处理设备中断 |

#### 典型名称模式

```
driver
cuda
npu
gpu
device
interrupt
```

#### 性能关注点

1. **设备利用率**：设备是否充分利用
2. **中断延迟**：中断处理的及时性
3. **命令队列**：命令队列的深度和延迟
4. **内存拷贝**：主机与设备间的内存拷贝

#### 优化方向

- 使用异步操作减少等待
- 优化命令提交批处理
- 使用零拷贝技术
- 调整中断合并策略

---

### 4. 框架线程 (Framework Thread)

#### 定义
AI 框架的控制和管理线程，负责调度、数据加载等。

#### 特征

| 特征维度 | 典型值 | 判定标准 |
|---------|-------|---------|
| CPU 使用率 | 低 (<30%) | 控制逻辑为主 |
| 用户态比例 | 高 | 框架代码执行 |
| 上下文切换 | 高 (>1000/s) | 同步和调度 |
| 锁等待 | 高 | 资源竞争 |
| IPC 活动 | 中等 | 进程间协调 |

#### 典型名称模式

```
main
scheduler
dataloader
controller
manager
coordinator
```

#### 性能关注点

1. **锁竞争**：框架内部锁的竞争情况
2. **调度开销**：任务调度的开销
3. **数据加载延迟**：数据加载是否成为瓶颈
4. **同步延迟**：屏障、条件变量的等待时间

#### 优化方向

- 减少锁粒度或使用无锁数据结构
- 优化调度算法
- 预取数据减少加载延迟
- 减少不必要的同步

---

## 分类方法

### 基于规则的分类

```python
def classify_thread(thread_profile):
    # 提取特征
    cpu_usage = thread_profile["cpu_usage"]
    user_ratio = thread_profile["user_time"] / thread_profile["total_time"]
    ctx_switch_rate = thread_profile["ctx_switches"]["total"] / thread_profile["duration"]
    io_wait = thread_profile["io_wait_time"] / thread_profile["total_time"]
    
    # 计算线程特征
    if cpu_usage > 70 and user_ratio > 0.8 and ctx_switch_rate < 100:
        return "计算线程"
    
    # 通信线程特征
    if 20 < cpu_usage < 50 and io_wait > 0.1:
        if has_network_activity(thread_profile):
            return "通信线程"
    
    # 驱动线程特征
    if cpu_usage < 20 and thread_profile["kernel_time"] / thread_profile["total_time"] > 0.5:
        if has_device_activity(thread_profile):
            return "驱动线程"
    
    # 框架线程特征
    if ctx_switch_rate > 1000 and thread_profile["lock_wait_time"] > 0:
        return "框架线程"
    
    return "其他线程"
```

### 基于名称的分类

```python
THREAD_NAME_PATTERNS = {
    "计算线程": [
        r"worker", r"compute", r"forward", r"backward",
        r"matmul", r"conv", r"gemm"
    ],
    "通信线程": [
        r"nccl", r"hccl", r"comm", r"send", r"recv",
        r"network", r"socket", r"rdma"
    ],
    "驱动线程": [
        r"driver", r"cuda", r"npu", r"gpu", r"device",
        r"interrupt"
    ],
    "框架线程": [
        r"main", r"scheduler", r"dataloader", r"controller",
        r"manager", r"coordinator"
    ]
}

def classify_by_name(thread_name):
    thread_name_lower = thread_name.lower()
    for thread_type, patterns in THREAD_NAME_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, thread_name_lower):
                return thread_type
    return "其他线程"
```

### 混合分类策略

```python
def classify_thread_hybrid(thread_profile):
    # 优先使用名称分类
    name_classification = classify_by_name(thread_profile["name"])
    
    # 使用特征分类验证
    feature_classification = classify_thread(thread_profile)
    
    # 如果名称和特征一致，直接返回
    if name_classification == feature_classification:
        return name_classification
    
    # 如果名称分类为"其他"，使用特征分类
    if name_classification == "其他线程":
        return feature_classification
    
    # 如果特征分类为"其他"，使用名称分类
    if feature_classification == "其他线程":
        return name_classification
    
    # 冲突时，根据置信度选择
    name_confidence = calculate_name_confidence(thread_profile)
    feature_confidence = calculate_feature_confidence(thread_profile)
    
    if name_confidence > feature_confidence:
        return name_classification
    else:
        return feature_classification
```

---

## 混合型线程处理

某些线程可能同时具有多种类型的特征，需要特殊处理。

### 常见混合类型

| 混合类型 | 特征 | 典型场景 |
|---------|------|---------|
| 计算-通信 | 高 CPU + 高网络 I/O | All-Reduce 计算 |
| 通信-驱动 | 中等 CPU + 高设备 I/O | GPU Direct RDMA |
| 框架-计算 | 中等 CPU + 高锁竞争 | 参数服务器 |

### 处理策略

```python
def handle_hybrid_thread(thread_profile):
    # 计算各类型的得分
    scores = {
        "计算线程": calculate_compute_score(thread_profile),
        "通信线程": calculate_communication_score(thread_profile),
        "驱动线程": calculate_driver_score(thread_profile),
        "框架线程": calculate_framework_score(thread_profile)
    }
    
    # 找出得分最高的两个类型
    top_two = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:2]
    
    # 如果两个得分都很高，标记为混合型
    if top_two[0][1] > 0.6 and top_two[1][1] > 0.4:
        return f"混合型 ({top_two[0][0]} + {top_two[1][0]})"
    
    # 否则返回主要类型
    return top_two[0][0]
```

---

## 分类统计示例

```python
def generate_thread_classification_report(threads):
    classification_counts = defaultdict(int)
    classification_stats = defaultdict(lambda: {
        "count": 0,
        "avg_cpu": [],
        "avg_ctx_switch": [],
        "avg_io_wait": []
    })
    
    for thread in threads:
        thread_type = classify_thread_hybrid(thread)
        classification_counts[thread_type] += 1
        
        stats = classification_stats[thread_type]
        stats["count"] += 1
        stats["avg_cpu"].append(thread["cpu_usage"])
        stats["avg_ctx_switch"].append(thread["ctx_switch_rate"])
        stats["avg_io_wait"].append(thread["io_wait_ratio"])
    
    # 计算平均值
    for thread_type, stats in classification_stats.items():
        stats["avg_cpu"] = sum(stats["avg_cpu"]) / len(stats["avg_cpu"])
        stats["avg_ctx_switch"] = sum(stats["avg_ctx_switch"]) / len(stats["avg_ctx_switch"])
        stats["avg_io_wait"] = sum(stats["avg_io_wait"]) / len(stats["avg_io_wait"])
    
    return classification_stats
```
