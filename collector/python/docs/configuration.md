# Configuration Guide

本指南描述 Witty Profiler 的运行时配置系统、JSON 配置结构和 CLI 覆盖机制。

## 配置加载优先级

配置按以下优先级加载（高优先级覆盖低优先级）：

1. **CLI 参数**（如 `--host`、`--port`、`--log-level`）
2. **配置文件**（`--config path.json`）
3. **框架默认值**（dataclass 默认值）

使用 `--dump-config` 可以导出解析后的完整配置：

```bash
witty-profiler --dump-config local/config.snapshot.json
```

## 配置文件格式

配置文件为 JSON 格式，对应的 dataclass 定义在 [src/witty_profiler/config_manager/configs](../src/witty_profiler/config_manager/configs) 目录下。

最小示例：

```json
{
  "tmp_dir": "local/run/witty_profiler",
  "server_config": {
    "server_addr": {"host": "0.0.0.0", "port": 18090}
  }
}
```

## 配置结构总览

```text
GlobalConfig
├── tmp_dir                      # 临时文件目录
├── server_config                # 服务端配置
│   ├── server_addr (host, port)
│   └── preferred_backend
├── collector_config             # 采集器配置
│   ├── disabled_collectors
│   ├── seed_graph_collectors
│   ├── remote_slaves
│   ├── socket_collector_config
│   ├── numa_collector_config
│   ├── rdma_collector_config
│   └── common_process_parent_collector_config
└── sniffer_config               # 底层嗅探器配置
    ├── socket_sniffer
    ├── cpu_sniffer
    ├── npu_sniffer
    ├── gpu_sniffer
    └── rdma_sniffer
```

## 各配置段说明

### `GlobalConfig`（顶层）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tmp_dir` | str | `"local/witty_profiler/run/"` | 临时文件和离线输出目录 |
| `server_config` | ServerConfig | 见下 | 服务端配置 |
| `collector_config` | CollectorConfig | 见下 | 采集器配置 |
| `sniffer_config` | SnifferConfig | 见下 | 嗅探器配置 |

### `server_config`

定义在 [server_config.py](../src/witty_profiler/config_manager/configs/server_config.py)。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `server_addr.host` | str | `"0.0.0.0"` | 绑定地址 |
| `server_addr.port` | int | `18090` | 绑定端口 |
| `preferred_backend` | str \| null | `null` | 后端选择：`"FastAPIServer"` / `"OnlineDisabledServer"` / null（自动） |

### `collector_config`

定义在 [collector_config.py](../src/witty_profiler/config_manager/configs/collector_config.py)。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `disabled_collectors` | list[str] | `[]` | 要禁用的 Collector 类名列表 |
| `seed_graph_collectors` | list[str] | 见下方 | 允许提供种子图的 Collector 列表 |
| `remote_slaves` | list[RemoteSlaveConfig] | `[{"slave_addr": {"host": "127.0.0.1", "port": -1}}]` | 远程从节点地址（port=-1 表示模板禁用） |
| `start_nodes` | list | `[]` | 初始种子实体 |
| `socket_collector_config` | SocketCollectorConfig | 见下 | Socket 采集器配置 |
| `numa_collector_config` | NumaCollectorConfig | 见下 | NUMA 采集器配置 |
| `rdma_collector_config` | RDMACollectorConfig | 见下 | RDMA 采集器配置 |
| `common_process_parent_collector_config` | — | `single_node_parent_depth=1` | 公共父进程采集深度 |

**`seed_graph_collectors` 默认值**：

```text
NPUCollector, GPUCollector, RemoteCollector, NumaCollector, RDMACollector, StaticCollector, CommonProcessParentCollector
```

#### `socket_collector_config`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `enable_thread_node` | `true` | 是否创建线程级节点 |
| `min_thread_packet_threshold` | `10` | 线程节点的最小数据包阈值 |
| `enable_filter` | `true` | 是否启用连接过滤 |
| `filter_conn_packet_cnt` | `5` | 连接的最小数据包数 |
| `filter_conn_data_size` | `240` | 连接的最小数据量 |

#### `numa_collector_config`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `enable_thread_node` | `true` | 是否创建线程级节点 |
| `min_thread_ctxt_switch_pct_thresh` | `0.1` | 上下文切换百分比阈值 |
| `min_thread_cpu_pct_thresh` | `0.1` | CPU 使用率百分比阈值 |

#### `rdma_collector_config`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `enable_thread_node` | `true` | 是否创建线程级节点 |
| `min_thread_rdma_ops_thresh` | `10` | RDMA 操作数阈值 |

### `sniffer_config`

定义在 [sniffer_config.py](../src/witty_profiler/config_manager/configs/sniffer_config.py)。

#### `socket_sniffer`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `socket_sniffer_binary_path` | 自动解析 | eBPF 二进制路径（默认 `<pkg>/binary/socket/socket_sniffer`） |
| `msg_style` | `"csv"` | 输出格式（csv / msgspec） |
| `monitor_report_maximum_interval_by_second` | `2.0` | 监控报告最大间隔 |
| `data_file_path` | `"witty_profiler.socket_sniffer.csv"` | 数据文件路径 |
| `maximum_log_file_size_in_mb` | `100` | 日志文件最大大小 |
| `maximum_rotation_cnt` | `3` | 日志轮转次数 |
| `maximum_dataframe_size_in_seconds` | `30` | 数据窗口时长 |
| `entry_buffer_size` | `20000` | 缓冲区大小 |

#### `cpu_sniffer`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `cache_miss_monitor_binary_path` | 自动解析 | Cache miss 监控二进制路径 |
| `cpu_sched_monitor_binary_path` | 自动解析 | 调度监控二进制路径 |
| `msg_style` | `"csv"` | 输出格式 |
| `monitor_report_maximum_interval_by_second` | `2.0` | 报告间隔 |
| `cache_data_file_path` | `"witty_profiler.cache_miss.csv"` | Cache 数据文件 |
| `sched_data_file_path` | `"witty_profiler.sched_monitor.csv"` | 调度数据文件 |
| `entry_buffer_size` | `20000` | 缓冲区大小 |

#### `npu_sniffer` / `gpu_sniffer`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `refresh_interval_by_second` | `30.0` | 设备刷新间隔（秒） |

#### `rdma_sniffer`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `update_interval_by_second` | `10.0` | RDMA 统计更新间隔（秒） |

## CLI 覆盖参数

这些参数在运行时覆盖配置文件的值：

| CLI 参数 | 覆盖的配置项 | 说明 |
|----------|-------------|------|
| `--host` | `server_config.server_addr.host` | 绑定地址 |
| `--port` | `server_config.server_addr.port` | 绑定端口 |
| `--config PATH` | 整个配置文件 | 加载指定 JSON 配置 |
| `--log-level` | 日志级别 | VERBOSE/DEBUG/INFO/REPORT/WARNING/ERROR/CRITICAL |
| `--offline` | 运行模式 | 离线模式（无 HTTP 服务） |
| `--duration` | 离线时长 | 离线采集持续时间（默认 10.0 秒） |
| `--pid` | `collector_config.start_nodes` | 指定监控的目标进程 PID |
| `--dump-config` | — | 导出配置为 JSON 并退出 |
| `--verify` | — | 校验 sniffer 二进制并退出 |
| `--view-graph` | — | 查看压缩图文件并退出 |

完整 CLI 说明参见 [Running Witty Profiler](user-guide/running.md)。

## 配置文件示例

完整示例可参考 [configs/config.sample.json](../configs/config.sample.json)。

```json
{
  "tmp_dir": "local/run/witty_profiler",
  "server_config": {
    "server_addr": {"host": "0.0.0.0", "port": 18090},
    "preferred_backend": null
  },
  "sniffer_config": {
    "socket_sniffer": {
      "monitor_report_maximum_interval_by_second": 2.0
    },
    "cpu_sniffer": {
      "cache_miss_monitor_binary_path": "src/witty_profiler/binary/cache_miss/cache_miss_monitor",
      "cpu_sched_monitor_binary_path": "src/witty_profiler/binary/cpu_sched/sched_monitor"
    },
    "gpu_sniffer": {
      "refresh_interval_by_second": 30.0
    },
    "rdma_sniffer": {
      "update_interval_by_second": 10.0
    }
  },
  "collector_config": {
    "disabled_collectors": [],
    "seed_graph_collectors": [
      "NPUCollector", "GPUCollector", "RemoteCollector",
      "NumaCollector", "RDMACollector", "StaticCollector",
      "CommonProcessParentCollector"
    ],
    "remote_slaves": [
      {"slave_addr": {"host": "127.0.0.1", "port": -1}, "query_interval_by_second": 10.0}
    ],
    "socket_collector_config": {
      "enable_thread_node": true,
      "enable_filter": true,
      "filter_conn_packet_cnt": 5
    }
  }
}
```
