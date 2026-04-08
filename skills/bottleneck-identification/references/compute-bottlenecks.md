# 计算瓶颈识别

本文档详细描述计算瓶颈的识别方法，包括 CPU Starvation、NPU Idle 等问题。

## 目录

1. [计算资源概述](#计算资源概述)
2. [计算瓶颈类型](#计算瓶颈类型)
3. [识别方法](#识别方法)
4. [优化策略](#优化策略)

---

## 计算资源概述

### 计算资源类型

| 资源类型 | 特点 | 适用场景 |
|---------|------|---------|
| **CPU** | 通用计算、灵活 | 控制逻辑、数据预处理 |
| **NPU** | AI 专用、高效 | 深度学习训练推理 |
| **GPU** | 并行计算、通用 | 图形、科学计算、AI |

### 计算性能指标

| 指标 | CPU | NPU | GPU |
|-----|-----|-----|-----|
| 峰值算力 | TFLOPS | TOPS | TFLOPS |
| 利用率 | 0-100% | 0-100% | 0-100% |
| IPC | 0-3+ | N/A | N/A |
| SM 效率 | N/A | N/A | 0-100% |

---

## 计算瓶颈类型

### 1. CPU Starvation (CPU 饥饿)

#### 定义
CPU 利用率过低，计算资源未被充分利用。

#### 识别特征

**指标阈值**:
- CPU 利用率 < 30%
- 低上下文切换率
- 高 I/O 等待时间

**数据来源**:
- sched_monitor 数据
- /proc/stat
- top/htop

#### 严重性判定

```python
def assess_cpu_starvation_severity(cpu_usage, io_wait_ratio):
    if cpu_usage < 20:
        return "Critical"
    elif cpu_usage < 30:
        return "Warning"
    elif cpu_usage < 40:
        return "Notice"
    else:
        return "Info"
```

#### 根因分析

| 根因 | 特征 | 解决方案 |
|-----|------|---------|
| **线程数不足** | 线程数 < CPU 核数 | 增加工作线程 |
| **I/O 阻塞** | 高 I/O 等待 | 异步 I/O |
| **锁竞争** | 高锁等待时间 | 减少锁粒度 |
| **任务不足** | 任务队列空 | 增加任务生成速度 |

#### 优化建议

1. **增加并发度**
   ```python
   # 增加工作线程
   import multiprocessing
   
   num_workers = multiprocessing.cpu_count()
   with ThreadPoolExecutor(max_workers=num_workers) as executor:
       futures = [executor.submit(task, item) for item in items]
   ```

2. **使用异步 I/O**
   ```python
   # 异步 I/O 减少阻塞
   import asyncio
   
   async def process_async(items):
       tasks = [process_item(item) for item in items]
       return await asyncio.gather(*tasks)
   ```

3. **优化锁**
   ```python
   # 减少锁粒度
   from concurrent.futures import ThreadPoolExecutor
   import threading
   
   class FineGrainedLock:
       def __init__(self, num_shards=16):
           self.locks = [threading.Lock() for _ in range(num_shards)]
       
       def get_lock(self, key):
           return self.locks[hash(key) % len(self.locks)]
   ```

---

### 2. NPU Idle (NPU 空闲)

#### 定义
NPU 利用率过低，AI 加速器未被充分利用。

#### 识别特征

**指标阈值**:
- NPU 利用率 < 50%
- 低内存带宽使用
- 低 PCIe 带宽使用

**数据来源**:
- NPU 驱动统计
- npu-smi 工具
- 应用监控

#### 严重性判定

```python
def assess_npu_idle_severity(npu_usage, memory_bandwidth):
    if npu_usage < 30:
        return "Critical"
    elif npu_usage < 50:
        return "Warning"
    elif npu_usage < 70:
        return "Notice"
    else:
        return "Info"
```

#### 根因分析

| 根因 | 特征 | 解决方案 |
|-----|------|---------|
| **数据加载慢** | DataLoader 瓶颈 | 优化数据加载 |
| **模型过小** | 计算量不足 | 增加批次大小 |
| **CPU 预处理慢** | CPU 成为瓶颈 | 优化预处理 |
| **同步等待** | 多卡同步慢 | 优化同步策略 |

#### 优化建议

1. **优化数据加载**
   ```python
   # PyTorch DataLoader 优化
   dataloader = DataLoader(
       dataset,
       batch_size=256,        # 增大批次
       num_workers=8,         # 增加 worker
       pin_memory=True,       # 锁页内存
       prefetch_factor=2      # 预取
   )
   ```

2. **增加批次大小**
   ```python
   # 增大批次提高 NPU 利用率
   batch_size = 256  # 或更大
   
   # 使用梯度累积模拟大批次
   accumulation_steps = 4
   for i, batch in enumerate(dataloader):
       loss = model(batch)
       loss = loss / accumulation_steps
       loss.backward()
       
       if (i + 1) % accumulation_steps == 0:
           optimizer.step()
           optimizer.zero_grad()
   ```

3. **优化预处理**
   ```python
   # 使用 GPU/NPU 预处理
   import torchvision.transforms as T
   
   transform = T.Compose([
       T.Resize(256),
       T.RandomCrop(224),
       T.ToTensor(),
       T.Normalize(mean, std)
   ])
   
   # 使用 DALI 加速
   from nvidia.dali import pipeline_def
   import nvidia.dali.types as types
   import nvidia.dali.fn as fn
   
   @pipeline_def
   def create_pipeline():
       images, labels = fn.readers.file(file_root=data_dir)
       images = fn.decoders.image(images, device="mixed")
       images = fn.resize(images, resize_x=256, resize_y=256)
       return images, labels
   ```

---

### 3. Compute Bound (计算受限)

#### 定义
计算密集型任务，算力不足成为瓶颈。

#### 识别特征

**指标阈值**:
- CPU/NPU 利用率 > 90%
- 高 IPC (> 1.5)
- 低缓存缺失率

**数据来源**:
- 性能计数器
- 应用监控
- 算力统计

#### 严重性判定

```python
def assess_compute_bound_severity(compute_usage, ipc):
    if compute_usage > 95 and ipc > 2.0:
        return "Critical"
    elif compute_usage > 90 and ipc > 1.5:
        return "Warning"
    elif compute_usage > 85:
        return "Notice"
    else:
        return "Info"
```

#### 根因分析

| 根因 | 特征 | 解决方案 |
|-----|------|---------|
| **模型计算量大** | FLOPs 高 | 模型压缩 |
| **算法复杂度高** | 时间复杂度高 | 优化算法 |
| **硬件算力不足** | 硬件性能低 | 升级硬件 |
| **并行度不足** | 串行计算多 | 并行化 |

#### 优化建议

1. **模型优化**
   ```python
   # 模型剪枝
   import torch.nn.utils.prune as prune
   
   # 剪枝 30% 的权重
   prune.l1_unstructured(model.conv1, name='weight', amount=0.3)
   
   # 模型量化
   model = torch.quantization.quantize_dynamic(
       model, {torch.nn.Linear}, dtype=torch.qint8
   )
   ```

2. **算法优化**
   ```python
   # 使用高效算子
   import torch
   
   # 优化前: 逐元素操作
   for i in range(N):
       result[i] = torch.matmul(A[i], B[i])
   
   # 优化后: 批量操作
   result = torch.bmm(A, B)  # 批量矩阵乘法
   ```

3. **增加计算资源**
   - 使用更多 NPU/GPU
   - 使用更高性能的硬件
   - 使用分布式训练

---

### 4. CPU Overload (CPU 过载)

#### 定义
CPU 利用率过高，导致调度延迟和响应慢。

#### 识别特征

**指标阈值**:
- CPU 利用率 > 95%
- 高负载 (load average > CPU 核数)
- 高非自愿上下文切换

**数据来源**:
- /proc/loadavg
- sched_monitor
- top/htop

#### 严重性判定

```python
def assess_cpu_overload_severity(cpu_usage, load_avg, num_cores):
    load_ratio = load_avg / num_cores
    if cpu_usage > 95 and load_ratio > 2.0:
        return "Critical"
    elif cpu_usage > 90 and load_ratio > 1.5:
        return "Warning"
    elif cpu_usage > 85 and load_ratio > 1.2:
        return "Notice"
    else:
        return "Info"
```

#### 优化建议

1. **减少线程数**
   ```python
   # 限制线程池大小
   max_workers = multiprocessing.cpu_count()
   executor = ThreadPoolExecutor(max_workers=max_workers)
   ```

2. **使用进程池**
   ```python
   # CPU 密集型任务使用进程池
   from multiprocessing import Pool
   
   with Pool(processes=multiprocessing.cpu_count()) as pool:
       results = pool.map(cpu_intensive_task, items)
   ```

3. **任务优先级**
   ```python
   # 设置任务优先级
   import os
   import sys
   
   # 降低优先级
   os.nice(10)
   
   # 或使用 cgroups 限制 CPU
   # cgcreate -g cpu:/low_priority
   # cgset -r cpu.cfs_quota_us=50000 low_priority
   ```

---

### 5. NPU Thermal Throttling (NPU 降频)

#### 定义
NPU 温度过高导致降频，性能下降。

#### 识别特征

**指标阈值**:
- NPU 温度 > 85°C
- NPU 频率 < 额定频率
- NPU 性能下降

**数据来源**:
- NPU 驱动
- 温度传感器
- 性能监控

#### 严重性判定

```python
def assess_thermal_throttling_severity(temperature, frequency_ratio):
    if temperature > 90 or frequency_ratio < 0.8:
        return "Critical"
    elif temperature > 85 or frequency_ratio < 0.9:
        return "Warning"
    elif temperature > 80:
        return "Notice"
    else:
        return "Info"
```

#### 优化建议

1. **改善散热**
   - 清理灰尘
   - 增加风扇转速
   - 改善机箱风道

2. **降低功耗**
   ```python
   # 降低 NPU 功耗限制
   # nvidia-smi -pl 250  # 限制 GPU 功耗 250W
   ```

3. **减少计算密度**
   - 降低批次大小
   - 增加间隔时间

---

## 识别方法

### 基于 sched_monitor 数据

```python
def identify_compute_bottlenecks_from_sched(sched_data):
    """
    从 sched_monitor 数据识别计算瓶颈
    """
    bottlenecks = []
    
    # 按 PID 分组
    grouped = sched_data.groupby('tgid')
    
    for pid, group in grouped:
        # 计算 CPU 使用率
        cpu_time = group['time_ns'].sum()
        duration = group['window_end_ns'].max() - group['window_start_ns'].min()
        cpu_usage = cpu_time / duration * 100
        
        # 判定瓶颈
        if cpu_usage < 30:
            bottlenecks.append({
                "type": "CPU Starvation",
                "severity": assess_cpu_starvation_severity(cpu_usage, 0),
                "pid": pid,
                "cpu_usage": cpu_usage
            })
        elif cpu_usage > 90:
            bottlenecks.append({
                "type": "Compute Bound",
                "severity": "Warning",
                "pid": pid,
                "cpu_usage": cpu_usage
            })
    
    return bottlenecks
```

### 基于 NPU 监控数据

```python
def identify_npu_bottlenecks(npu_stats):
    """
    从 NPU 统计数据识别瓶颈
    """
    bottlenecks = []
    
    for npu_id, stats in npu_stats.items():
        utilization = stats['utilization']
        temperature = stats['temperature']
        frequency = stats['frequency']
        rated_frequency = stats['rated_frequency']
        
        # NPU 空闲
        if utilization < 50:
            bottlenecks.append({
                "type": "NPU Idle",
                "severity": assess_npu_idle_severity(utilization, 0),
                "npu_id": npu_id,
                "utilization": utilization
            })
        
        # NPU 过载
        elif utilization > 95:
            bottlenecks.append({
                "type": "NPU Overload",
                "severity": "Warning",
                "npu_id": npu_id,
                "utilization": utilization
            })
        
        # 降频
        frequency_ratio = frequency / rated_frequency
        if temperature > 80 or frequency_ratio < 1.0:
            bottlenecks.append({
                "type": "NPU Thermal Throttling",
                "severity": assess_thermal_throttling_severity(temperature, frequency_ratio),
                "npu_id": npu_id,
                "temperature": temperature,
                "frequency_ratio": frequency_ratio
            })
    
    return bottlenecks
```

---

## 优化策略

### 通用优化原则

1. **提高利用率**
   - 增加并发度
   - 减少阻塞
   - 优化调度

2. **减少计算量**
   - 模型压缩
   - 算法优化
   - 缓存结果

3. **增加算力**
   - 升级硬件
   - 分布式训练
   - 使用加速器

4. **平衡负载**
   - 任务调度
   - 负载均衡
   - 资源隔离

### 性能监控

持续监控计算资源：

```python
def monitor_compute_performance(interval=10):
    while True:
        # 收集计算指标
        cpu_stats = collect_cpu_stats()
        npu_stats = collect_npu_stats()
        gpu_stats = collect_gpu_stats()
        
        # 检测瓶颈
        bottlenecks = detect_compute_bottlenecks(
            cpu_stats, npu_stats, gpu_stats
        )
        
        # 告警
        if bottlenecks:
            alert_bottlenecks(bottlenecks)
        
        time.sleep(interval)
```
