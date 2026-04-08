# 上下文切换与竞争分析

本文档详细描述线程上下文切换的分析方法和竞争问题的诊断策略。

## 目录

1. [上下文切换基础](#上下文切换基础)
2. [上下文切换分析](#上下文切换分析)
3. [竞争问题诊断](#竞争问题诊断)
4. [优化策略](#优化策略)

---

## 上下文切换基础

### 上下文切换类型

| 类型 | 原因 | 触发方式 | 性能影响 |
|-----|------|---------|---------|
| **自愿切换** | 线程主动让出 CPU | sleep、I/O 等待、锁等待 | 中等 |
| **非自愿切换** | 调度器强制切换 | 时间片耗尽、优先级抢占 | 高 |

### 数据来源

上下文切换数据来自 `/proc/[pid]/status`:

```bash
$ cat /proc/12345/status
...
voluntary_ctxt_switches:	1523
nonvoluntary_ctxt_switches:	892
...
```

### 关键指标

| 指标 | 计算方法 | 正常范围 | 热点阈值 |
|-----|---------|---------|---------|
| 总切换率 | (voluntary + involuntary) / duration | < 100/s | > 5000/s |
| 自愿切换率 | voluntary / duration | < 50/s | > 1000/s |
| 非自愿切换率 | involuntary / duration | < 50/s | > 5000/s |
| 自愿切换占比 | voluntary / total | 0.3-0.7 | > 0.8 或 < 0.2 |

---

## 上下文切换分析

### 分析流程

```python
def analyze_context_switches(thread):
    """
    分析线程的上下文切换情况
    
    Returns:
        {
            "total_rate": float,
            "voluntary_rate": float,
            "involuntary_rate": float,
            "voluntary_ratio": float,
            "severity": str,
            "cause": str,
            "recommendations": List[str]
        }
    """
    voluntary = thread["ctx_switches"]["voluntary"]
    involuntary = thread["ctx_switches"]["involuntary"]
    total = voluntary + involuntary
    duration = thread.get("duration", 1.0)
    
    # 计算切换率
    total_rate = total / duration
    voluntary_rate = voluntary / duration
    involuntary_rate = involuntary / duration
    voluntary_ratio = voluntary / total if total > 0 else 0
    
    # 判定严重程度
    if total_rate > 10000:
        severity = "严重"
    elif total_rate > 5000:
        severity = "警告"
    elif total_rate > 1000:
        severity = "注意"
    else:
        severity = "正常"
    
    # 分析原因
    if voluntary_ratio > 0.8:
        cause = "I/O 或同步等待过多"
        recommendations = [
            "检查是否存在不必要的 sleep 或 yield",
            "使用异步 I/O 替代同步 I/O",
            "减少锁持有时间",
            "检查条件变量的等待条件"
        ]
    elif voluntary_ratio < 0.2:
        cause = "CPU 竞争激烈"
        recommendations = [
            "减少线程数量或 CPU 过度订阅",
            "调整线程优先级",
            "使用 CPU 亲和性减少迁移",
            "检查是否有 CPU 密集型任务干扰"
        ]
    else:
        cause = "混合原因"
        recommendations = [
            "综合分析 I/O 和 CPU 使用情况",
            "考虑分离 I/O 密集和 CPU 密集任务"
        ]
    
    return {
        "total_rate": total_rate,
        "voluntary_rate": voluntary_rate,
        "involuntary_rate": involuntary_rate,
        "voluntary_ratio": voluntary_ratio,
        "severity": severity,
        "cause": cause,
        "recommendations": recommendations
    }
```

### 自愿上下文切换分析

自愿切换通常由以下原因引起：

#### 1. I/O 等待

**特征**:
- 高自愿切换率
- 高 I/O 等待时间
- 网络/磁盘活动频繁

**诊断**:

```python
def diagnose_io_wait(thread):
    voluntary_rate = thread["ctx_switches"]["voluntary"] / thread["duration"]
    io_wait_ratio = thread["io_wait_time"] / thread["total_time"]
    
    if voluntary_rate > 1000 and io_wait_ratio > 0.3:
        return {
            "has_issue": True,
            "issue_type": "I/O 等待过多",
            "severity": "警告",
            "details": f"自愿切换率 {voluntary_rate:.0f}/s, I/O 等待占比 {io_wait_ratio*100:.1f}%",
            "recommendations": [
                "使用异步 I/O 或非阻塞 I/O",
                "增加 I/O 缓冲区大小",
                "使用 I/O 多路复用 (epoll/select)",
                "考虑批量 I/O 操作"
            ]
        }
    
    return {"has_issue": False}
```

---

#### 2. 锁等待

**特征**:
- 高自愿切换率
- 锁竞争指标高
- 同步原语使用频繁

**诊断**:

```python
def diagnose_lock_wait(thread):
    voluntary_rate = thread["ctx_switches"]["voluntary"] / thread["duration"]
    lock_wait_time = thread.get("lock_wait_time", 0)
    total_time = thread["total_time"]
    
    if voluntary_rate > 500 and lock_wait_time / total_time > 0.2:
        return {
            "has_issue": True,
            "issue_type": "锁等待过多",
            "severity": "警告",
            "details": f"自愿切换率 {voluntary_rate:.0f}/s, 锁等待占比 {lock_wait_time/total_time*100:.1f}%",
            "recommendations": [
                "减少锁粒度",
                "使用读写锁替代互斥锁",
                "考虑无锁数据结构",
                "减少临界区代码"
            ]
        }
    
    return {"has_issue": False}
```

---

#### 3. 条件变量等待

**特征**:
- 高自愿切换率
- 条件变量使用频繁
- 任务队列相关

**诊断**:

```python
def diagnose_condvar_wait(thread):
    voluntary_rate = thread["ctx_switches"]["voluntary"] / thread["duration"]
    condvar_waits = thread.get("condvar_waits", 0)
    
    if voluntary_rate > 500 and condvar_waits > 100:
        return {
            "has_issue": True,
            "issue_type": "条件变量等待过多",
            "severity": "注意",
            "details": f"自愿切换率 {voluntary_rate:.0f}/s, 条件变量等待次数 {condvar_waits}",
            "recommendations": [
                "检查条件变量的等待条件是否合理",
                "考虑使用超时等待避免无限等待",
                "优化任务队列的实现"
            ]
        }
    
    return {"has_issue": False}
```

---

### 非自愿上下文切换分析

非自愿切换通常由以下原因引起：

#### 1. CPU 竞争

**特征**:
- 高非自愿切换率
- CPU 使用率高
- 多个 CPU 密集型线程

**诊断**:

```python
def diagnose_cpu_contention(thread):
    involuntary_rate = thread["ctx_switches"]["involuntary"] / thread["duration"]
    cpu_usage = thread["cpu_usage"]
    
    if involuntary_rate > 5000 and cpu_usage > 70:
        return {
            "has_issue": True,
            "issue_type": "CPU 竞争激烈",
            "severity": "严重",
            "details": f"非自愿切换率 {involuntary_rate:.0f}/s, CPU 使用率 {cpu_usage:.1f}%",
            "recommendations": [
                "减少线程数量，避免 CPU 过度订阅",
                "调整线程优先级",
                "使用 CPU 亲和性绑定线程",
                "分离 CPU 密集型和 I/O 密集型任务"
            ]
        }
    
    return {"has_issue": False}
```

---

#### 2. 优先级抢占

**特征**:
- 高非自愿切换率
- 存在高优先级线程
- 实时任务干扰

**诊断**:

```python
def diagnose_priority_preemption(thread):
    involuntary_rate = thread["ctx_switches"]["involuntary"] / thread["duration"]
    thread_priority = thread.get("priority", 0)
    
    if involuntary_rate > 3000 and thread_priority < 0:  # 低优先级
        return {
            "has_issue": True,
            "issue_type": "优先级抢占",
            "severity": "警告",
            "details": f"非自愿切换率 {involuntary_rate:.0f}/s, 线程优先级 {thread_priority}",
            "recommendations": [
                "提高线程优先级",
                "使用实时调度策略 (SCHED_FIFO/RT)",
                "隔离高优先级任务到专用 CPU"
            ]
        }
    
    return {"has_issue": False}
```

---

## 竞争问题诊断

### 锁竞争分析

#### 锁竞争指标

| 指标 | 数据来源 | 告警阈值 |
|-----|---------|---------|
| 锁等待时间 | perf/ftrace | > 20% 总时间 |
| 锁持有时间 | perf/ftrace | > 100ms |
| 锁竞争次数 | perf/ftrace | > 1000/s |

#### 锁竞争诊断流程

```python
def diagnose_lock_contention(thread):
    """
    诊断锁竞争问题
    
    Returns:
        {
            "has_contention": bool,
            "contention_level": str,
            "hot_locks": List[dict],
            "recommendations": List[str]
        }
    """
    lock_stats = thread.get("lock_stats", {})
    
    if not lock_stats:
        return {"has_contention": False}
    
    # 分析每个锁的竞争情况
    hot_locks = []
    for lock_name, stats in lock_stats.items():
        wait_time_ratio = stats["wait_time"] / thread["total_time"]
        contention_count = stats["contention_count"]
        
        if wait_time_ratio > 0.1 or contention_count > 100:
            hot_locks.append({
                "lock_name": lock_name,
                "wait_time_ratio": wait_time_ratio,
                "contention_count": contention_count,
                "avg_wait_time": stats["wait_time"] / contention_count if contention_count > 0 else 0
            })
    
    if not hot_locks:
        return {"has_contention": False}
    
    # 判定竞争级别
    max_wait_ratio = max(lock["wait_time_ratio"] for lock in hot_locks)
    
    if max_wait_ratio > 0.3:
        contention_level = "严重"
    elif max_wait_ratio > 0.15:
        contention_level = "警告"
    else:
        contention_level = "轻微"
    
    # 生成建议
    recommendations = []
    for lock in hot_locks:
        if lock["wait_time_ratio"] > 0.2:
            recommendations.append(f"优化锁 '{lock['lock_name']}': 减少锁粒度或使用无锁数据结构")
    
    return {
        "has_contention": True,
        "contention_level": contention_level,
        "hot_locks": sorted(hot_locks, key=lambda x: x["wait_time_ratio"], reverse=True),
        "recommendations": recommendations
    }
```

---

### 资源竞争分析

#### 资源类型

| 资源类型 | 竞争表现 | 诊断方法 |
|---------|---------|---------|
| **CPU** | 非自愿切换高 | 分析 CPU 使用率和调度延迟 |
| **内存** | 页错误高、NUMA 远端访问 | 分析内存带宽和 NUMA 访问 |
| **I/O** | I/O 等待高 | 分析 I/O 队列深度和延迟 |
| **网络** | 网络延迟高 | 分析网络带宽和包重传 |

#### CPU 竞争诊断

```python
def diagnose_cpu_contention_detailed(thread, system_info):
    """
    详细诊断 CPU 竞争
    
    Args:
        thread: 线程信息
        system_info: 系统级信息 (所有线程)
    """
    # 计算系统级 CPU 负载
    total_cpu_usage = sum(t["cpu_usage"] for t in system_info["threads"])
    cpu_count = system_info["cpu_count"]
    
    # CPU 过度订阅检测
    oversubscription_ratio = total_cpu_usage / (cpu_count * 100)
    
    if oversubscription_ratio > 1.5:
        return {
            "has_contention": True,
            "contention_type": "CPU 过度订阅",
            "severity": "严重",
            "details": f"CPU 负载 {total_cpu_usage:.1f}% / {cpu_count} 核 = {oversubscription_ratio:.2f}x 过度订阅",
            "recommendations": [
                f"减少线程数量 (当前 {len(system_info['threads'])} 个线程)",
                "使用线程池限制并发度",
                "分离 CPU 密集型任务"
            ]
        }
    
    return {"has_contention": False}
```

---

## 优化策略

### 策略 1: 减少 I/O 等待

**适用场景**: 高自愿切换 + 高 I/O 等待

**实施方法**:

```python
# 优化前: 同步 I/O
def read_data_sync():
    with open("data.txt", "r") as f:
        data = f.read()  # 阻塞等待
    return data

# 优化后: 异步 I/O
import asyncio

async def read_data_async():
    with open("data.txt", "r") as f:
        data = await asyncio.to_thread(f.read)  # 非阻塞
    return data

# 或使用 aiofiles
import aiofiles

async def read_data_aiofiles():
    async with aiofiles.open("data.txt", "r") as f:
        data = await f.read()
    return data
```

**效果**:
- 自愿切换率降低 60-80%
- I/O 吞吐量提升 2-3 倍

---

### 策略 2: 减少锁竞争

**适用场景**: 高自愿切换 + 高锁等待

**实施方法**:

```python
# 优化前: 粗粒度锁
class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}
    
    def update(self, key, value):
        with self.lock:  # 锁住整个字典
            self.data[key] = value

# 优化后: 细粒度锁
from concurrent.futures import ThreadPoolExecutor
import threading

class SharedDataOptimized:
    def __init__(self, num_shards=16):
        self.shards = [{} for _ in range(num_shards)]
        self.locks = [threading.Lock() for _ in range(num_shards)]
    
    def _get_shard(self, key):
        return hash(key) % len(self.shards)
    
    def update(self, key, value):
        shard_id = self._get_shard(key)
        with self.locks[shard_id]:  # 只锁住一个分片
            self.shards[shard_id][key] = value

# 优化后: 无锁数据结构
from queue import Queue
from threading import Thread

class SharedDataLockFree:
    def __init__(self):
        self.queue = Queue()
        self.data = {}
        self.worker = Thread(target=self._process_updates, daemon=True)
        self.worker.start()
    
    def _process_updates(self):
        while True:
            key, value = self.queue.get()
            self.data[key] = value
            self.queue.task_done()
    
    def update(self, key, value):
        self.queue.put((key, value))
```

**效果**:
- 锁等待时间降低 70-90%
- 吞吐量提升 3-5 倍

---

### 策略 3: 减少 CPU 竞争

**适用场景**: 高非自愿切换 + CPU 竞争

**实施方法**:

```python
# 优化前: 过多线程
def process_data_parallel(data, num_threads=32):
    chunk_size = len(data) // num_threads
    threads = []
    
    for i in range(num_threads):
        chunk = data[i*chunk_size : (i+1)*chunk_size]
        t = threading.Thread(target=process_chunk, args=(chunk,))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()

# 优化后: 使用线程池 + CPU 亲和性
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import os

def process_data_optimized(data):
    # 使用 CPU 核心数的线程
    num_workers = multiprocessing.cpu_count()
    
    # 设置 CPU 亲和性
    def process_with_affinity(chunk, cpu_id):
        os.sched_setaffinity(0, [cpu_id])
        return process_chunk(chunk)
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        chunk_size = len(data) // num_workers
        futures = []
        
        for i in range(num_workers):
            chunk = data[i*chunk_size : (i+1)*chunk_size]
            future = executor.submit(process_with_affinity, chunk, i)
            futures.append(future)
        
        results = [f.result() for f in futures]
    
    return results
```

**效果**:
- 非自愿切换率降低 50-70%
- CPU 利用率提升 20-30%

---

### 策略 4: 批量处理

**适用场景**: 高切换率 + 小任务频繁

**实施方法**:

```python
# 优化前: 逐个处理
def process_items(items):
    for item in items:
        process_single(item)  # 每次都可能切换

# 优化后: 批量处理
def process_items_batch(items, batch_size=100):
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        process_batch(batch)  # 减少切换次数
```

**效果**:
- 上下文切换率降低 80-90%
- 吞吐量提升 2-4 倍

---

## 监控与告警

### 监控指标

```python
def monitor_context_switches(pid, interval=10):
    """
    持续监控进程的上下文切换
    """
    prev_voluntary = 0
    prev_involuntary = 0
    prev_time = time.time()
    
    while True:
        # 读取当前值
        status = read_proc_status(pid)
        voluntary = status["voluntary_ctxt_switches"]
        involuntary = status["nonvoluntary_ctxt_switches"]
        current_time = time.time()
        
        # 计算切换率
        duration = current_time - prev_time
        voluntary_rate = (voluntary - prev_voluntary) / duration
        involuntary_rate = (involuntary - prev_involuntary) / duration
        total_rate = voluntary_rate + involuntary_rate
        
        # 告警检查
        if total_rate > 5000:
            print(f"[ALERT] 高上下文切换率: {total_rate:.0f}/s")
        
        # 更新状态
        prev_voluntary = voluntary
        prev_involuntary = involuntary
        prev_time = current_time
        
        time.sleep(interval)
```

### 告警规则

| 指标 | 警告阈值 | 严重阈值 | 处理建议 |
|-----|---------|---------|---------|
| 总切换率 | > 5000/s | > 10000/s | 分析切换原因 |
| 自愿切换率 | > 1000/s | > 5000/s | 检查 I/O 和锁 |
| 非自愿切换率 | > 3000/s | > 5000/s | 减少 CPU 竞争 |
| 自愿切换占比 | > 0.8 或 < 0.2 | - | 检查线程类型 |
