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

### 性能影响评估

- **预计性能损失**: {performance_impact}
- **主要瓶颈类型**: {primary_bottleneck_type}

---

## 详细分析

### Layer 1: Compute (计算层)

#### 瓶颈 1.1: {bottleneck_name}

**严重性**: {severity}

**描述**:
{description}

**证据**:
{evidence_list}

**根因分析**:
{root_cause_analysis}

**影响评估**:
{impact_assessment}

**优化建议**:
{recommendations}

---

### Layer 2: Memory (内存层)

(按相同格式列出瓶颈)

---

### Layer 3: Interconnect (互连层)

(按相同格式列出瓶颈)

---

### Layer 4: Network (网络层)

(按相同格式列出瓶颈)

---

### Layer 5: Storage (存储层)

(按相同格式列出瓶颈)

---

### Layer 6: Control Plane (控制平面层)

(按相同格式列出瓶颈)

---

### Layer 7: Data Plane (数据流处理层)

(按相同格式列出瓶颈)

---

## 优化建议优先级

### P0 - 紧急 (立即处理)

1. **{bottleneck_name}**
   - **操作**: {action}
   - **预期效果**: {expected_effect}
   - **实施时间**: {implementation_time}

### P1 - 重要 (本周处理)

1. **{bottleneck_name}**
   - **操作**: {action}
   - **预期效果**: {expected_effect}
   - **实施时间**: {implementation_time}

### P2 - 建议 (本月处理)

1. **{bottleneck_name}**
   - **操作**: {action}
   - **预期效果**: {expected_effect}
   - **实施时间**: {implementation_time}

---

## 实施路线图

### 第一阶段: 紧急优化 (立即)

- [ ] {action_1}
- [ ] {action_2}

**预期收益**: {expected_benefit}

### 第二阶段: 重点优化 (本周)

- [ ] {action_1}
- [ ] {action_2}

**预期收益**: {expected_benefit}

### 第三阶段: 持续优化 (本月)

- [ ] {action_1}
- [ ] {action_2}

**预期收益**: {expected_benefit}

---

## 附录

### 数据来源

- **Anansi Graph**: {graph_path}
- **sched_monitor**: {sched_data_path}
- **cache_monitor**: {cache_data_path}
- **numa_access_info**: {numa_data_path}
- **网络监控**: {network_data_path}

### 分析方法

- **框架**: 7 层瓶颈诊断框架
- **方法**: 模式匹配 + 证据链构建
- **工具**: witty-profiler + 自定义分析脚本

### 性能基线

| 指标 | 当前值 | 基线值 | 差异 |
|-----|-------|--------|------|
| {metric_1} | {current_1} | {baseline_1} | {diff_1} |
| {metric_2} | {current_2} | {baseline_2} | {diff_2} |

### 参考资料

- [bottleneck-taxonomy.md](references/bottleneck-taxonomy.md)
- [compute-bottlenecks.md](references/compute-bottlenecks.md)
- [memory-bottlenecks.md](references/memory-bottlenecks.md)
- [communication-bottlenecks.md](references/communication-bottlenecks.md)
- [io-bottlenecks.md](references/io-bottlenecks.md)
- [report-generation.md](references/report-generation.md)

---

**报告生成者**: witty-profiler bottleneck-identification skill
**版本**: 1.0.0
**联系方式**: {contact_info}
