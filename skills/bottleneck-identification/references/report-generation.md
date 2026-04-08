# 瓶颈报告模板与最佳实践

本文档提供瓶颈诊断报告的模板和生成最佳实践。

## 目录

1. [报告结构](#报告结构)
2. [报告模板](#报告模板)
3. [最佳实践](#最佳实践)
4. [示例报告](#示例报告)

---

## 报告结构

### 标准报告结构

```
1. 执行摘要
   - 系统概况
   - 关键发现
   - 优先级建议

2. 详细分析
   - 按层次分组
   - 每个瓶颈的详细分析
   - 证据链

3. 优化建议
   - 按优先级排序
   - 具体操作步骤
   - 预期效果

4. 附录
   - 数据来源
   - 分析方法
   - 参考资料
```

---

## 报告模板

### 完整模板

```markdown
# AI 训练系统瓶颈诊断报告

**生成时间**: {timestamp}
**系统**: {system_name}
**分析范围**: {analysis_scope}

---

## 执行摘要

### 系统概况

- **节点数量**: {num_nodes}
- **NPU/GPU 数量**: {num_accelerators}
- **训练任务**: {training_task}
- **分析时长**: {duration}

### 关键发现

- **识别瓶颈总数**: {total_bottlenecks}
- **严重瓶颈 (P0)**: {critical_count}
- **警告瓶颈 (P1)**: {warning_count}
- **建议关注 (P2)**: {notice_count}

### 优先级建议

1. **紧急处理**: {critical_bottleneck_1}
2. **优先处理**: {warning_bottleneck_1}
3. **建议关注**: {notice_bottleneck_1}

---

## Layer 1: Compute (计算层)

### 瓶颈 1.1: NPU Idle

**严重性**: Critical

**描述**:
NPU 利用率仅 35%，远低于正常范围 (70-90%)，表明 AI 加速器未被充分利用。

**证据**:
- NPU 0 利用率: 32%
- NPU 1 利用率: 38%
- NPU 2 利用率: 35%
- NPU 3 利用率: 36%
- 平均利用率: 35.25%

**根因分析**:
- 数据加载速度慢，NPU 等待数据
- DataLoader worker 数量不足 (当前: 2)
- 磁盘 I/O 成为瓶颈

**影响**:
- 训练吞吐量下降 50%
- 训练时间延长 2 倍
- 资源浪费严重

**优化建议**:
1. **增加 DataLoader worker**
   ```python
   dataloader = DataLoader(
       dataset,
       batch_size=256,
       num_workers=8,      # 从 2 增加到 8
       pin_memory=True,
       prefetch_factor=2
   )
   ```
   预期效果: NPU 利用率提升至 70%+

2. **使用 SSD 存储**
   - 将数据集迁移到 NVMe SSD
   - 预期效果: 数据加载速度提升 3-5 倍

3. **使用内存缓存**
   ```python
   # 缓存热点数据到内存
   class CachedDataset(Dataset):
       def __init__(self, dataset, cache_size=10000):
           self.cache = {}
           self.cache_size = cache_size
   ```
   预期效果: 减少 80% 的磁盘读取

---

## Layer 2: Memory (内存层)

### 瓶颈 2.1: Memory Bandwidth Wall

**严重性**: Warning

**描述**:
内存带宽利用率达到 85%，接近饱和，可能成为性能瓶颈。

**证据**:
- DDR4 带宽利用率: 85%
- LLC 缓存缺失率: 35%
- 算术强度: 3.2 FLOP/Byte (低)

**根因分析**:
- 数据访问模式不缓存友好
- 多个进程竞争内存带宽
- 工作集超过 LLC 容量

**影响**:
- 内存访问延迟增加 30%
- CPU 等待内存时间占比 25%

**优化建议**:
1. **优化数据局部性**
   - 使用数据分块
   - 优化访问模式

2. **减少内存访问**
   - 算子融合
   - 数据复用

---

## Layer 3: Interconnect (互连层)

### 瓶颈 3.1: Cross-NUMA Access

**严重性**: Warning

**描述**:
跨 NUMA 访问比例达到 35%，导致高延迟。

**证据**:
- NUMA 远端访问比例: 35%
- CPU-MEM 相似度: 0.42
- 主 NUMA: NUMA 0, 内存 NUMA: NUMA 1

**根因分析**:
- 线程和内存 NUMA 亲和性不匹配
- 内存分配策略不当

**优化建议**:
```bash
numactl --cpunodebind=0 --membind=0 python train.py
```

---

## Layer 4: Network (网络层)

(无瓶颈)

---

## Layer 5: Storage (存储层)

### 瓶颈 5.1: Disk I/O Bottleneck

**严重性**: Critical

**描述**:
磁盘 I/O 成为数据加载瓶颈。

**证据**:
- 磁盘利用率: 92%
- I/O 等待时间: 25% CPU
- 平均 I/O 延迟: 85ms

**优化建议**:
- 升级到 NVMe SSD
- 使用分布式存储

---

## Layer 6: Control Plane (控制平面层)

(无瓶颈)

---

## Layer 7: Data Plane (数据流处理层)

### 瓶颈 7.1: Data Loading Bottleneck

**严重性**: Critical

**描述**:
数据加载时间占比 45%，远高于计算时间。

**证据**:
- 数据加载时间: 45% 总时间
- 计算时间: 40% 总时间
- DataLoader 线程利用率: 95%

**优化建议**:
- 增加 DataLoader worker
- 使用异步数据加载
- 预取数据

---

## 优化建议优先级

### P0 - 紧急 (立即处理)

1. **解决 NPU Idle 问题**
   - 操作: 增加 DataLoader worker 到 8
   - 预期效果: NPU 利用率提升至 70%+
   - 实施时间: 5 分钟

2. **解决磁盘 I/O 瓶颈**
   - 操作: 迁移数据到 NVMe SSD
   - 预期效果: I/O 速度提升 5 倍
   - 实施时间: 1 小时

### P1 - 重要 (本周处理)

1. **优化 NUMA 亲和性**
   - 操作: 使用 numactl 绑定
   - 预期效果: 跨 NUMA 访问降低至 10%
   - 实施时间: 10 分钟

2. **优化内存访问**
   - 操作: 数据分块 + 算子融合
   - 预期效果: 内存带宽降低至 60%
   - 实施时间: 1 天

### P2 - 建议 (本月处理)

1. **持续监控**
   - 部署性能监控系统
   - 建立性能基线

---

## 附录

### 数据来源

- Anansi Graph: /path/to/graph.json
- sched_monitor: /path/to/sched_data.csv
- cache_monitor: /path/to/cache_data.csv
- numa_access_info: /path/to/numa_data.json

### 分析方法

- 7 层瓶颈框架
- 模式匹配
- 证据链构建
- 根因分析

### 参考资料

- bottleneck-taxonomy.md
- compute-bottlenecks.md
- memory-bottlenecks.md
- communication-bottlenecks.md
```

---

## 最佳实践

### 1. 报告生成原则

#### 原则 1: 结构清晰

- 使用标准结构
- 层次分明
- 逻辑清晰

#### 原则 2: 证据充分

- 每个结论有数据支持
- 提供具体数值
- 展示数据来源

#### 原则 3: 建议可操作

- 具体的操作步骤
- 提供代码示例
- 说明预期效果

#### 原则 4: 优先级明确

- 按严重性排序
- 标注处理时间
- 说明依赖关系

### 2. 报告生成流程

```python
def generate_bottleneck_report(graph, analysis_results):
    """
    生成瓶颈诊断报告
    
    Args:
        graph: Anansi Graph
        analysis_results: 分析结果
    
    Returns:
        str: Markdown 格式的报告
    """
    report = []
    
    # 1. 执行摘要
    report.append(generate_executive_summary(graph, analysis_results))
    
    # 2. 详细分析
    for layer in range(1, 8):
        layer_bottlenecks = analysis_results.get_layer_bottlenecks(layer)
        if layer_bottlenecks:
            report.append(generate_layer_analysis(layer, layer_bottlenecks))
    
    # 3. 优化建议
    report.append(generate_recommendations(analysis_results))
    
    # 4. 附录
    report.append(generate_appendix(graph, analysis_results))
    
    return "\n".join(report)
```

### 3. 自动化生成

```python
class BottleneckReportGenerator:
    def __init__(self, template_path):
        self.template = load_template(template_path)
    
    def generate(self, graph, bottlenecks):
        # 填充模板
        report = self.template.format(
            timestamp=datetime.now().isoformat(),
            system_name=graph.get_system_name(),
            total_bottlenecks=len(bottlenecks),
            critical_count=sum(1 for b in bottlenecks if b.severity == "Critical"),
            warning_count=sum(1 for b in bottlenecks if b.severity == "Warning"),
            notice_count=sum(1 for b in bottlenecks if b.severity == "Notice"),
            # ... 其他字段
        )
        
        return report
```

---

## 示例报告

### 简化版报告

```markdown
# 瓶颈诊断报告

## 执行摘要

识别到 3 个瓶颈：
- 严重: 1 个 (NPU Idle)
- 警告: 2 个 (Memory Bandwidth Wall, Cross-NUMA Access)

## 关键瓶颈

### 1. NPU Idle (Critical)

**问题**: NPU 利用率仅 35%

**证据**: 
- NPU 0: 32%
- NPU 1: 38%

**建议**: 增加 DataLoader worker 到 8

### 2. Memory Bandwidth Wall (Warning)

**问题**: 内存带宽利用率 85%

**建议**: 优化数据局部性

### 3. Cross-NUMA Access (Warning)

**问题**: 跨 NUMA 访问 35%

**建议**: 使用 numactl 绑定

## 优先级建议

1. 立即处理 NPU Idle
2. 本周处理 NUMA 问题
3. 本周优化内存访问
```

---

## 报告质量检查

### 检查清单

- [ ] 执行摘要完整
- [ ] 每个瓶颈有严重性标注
- [ ] 每个瓶颈有证据支持
- [ ] 每个瓶颈有优化建议
- [ ] 优化建议有优先级
- [ ] 优化建议可操作
- [ ] 数据来源清晰
- [ ] 格式规范

### 质量评分

```python
def assess_report_quality(report):
    """
    评估报告质量
    
    Returns:
        float: 质量分数 [0, 100]
    """
    score = 0
    
    # 结构完整性 (30 分)
    if has_executive_summary(report):
        score += 10
    if has_detailed_analysis(report):
        score += 10
    if has_recommendations(report):
        score += 10
    
    # 证据充分性 (30 分)
    if all_bottlenecks_have_evidence(report):
        score += 15
    if evidence_has_data(report):
        score += 15
    
    # 建议可操作性 (30 分)
    if all_bottlenecks_have_recommendations(report):
        score += 15
    if recommendations_are_actionable(report):
        score += 15
    
    # 格式规范性 (10 分)
    if format_is_standard(report):
        score += 10
    
    return score
```
