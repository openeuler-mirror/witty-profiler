# Quick Start Tutorial

5 分钟内运行 Anansi 并采集第一份拓扑图。

## 前置条件

- Python 3.11+ 已安装
- Anansi 已安装（参见 [Installation Guide](installation.md)）
- （可选）HTTP 服务端依赖已安装

## Step 1: 基础拓扑采集

通过 `AnansiCore` 单例进行基础的编程式采集：

1. 获取 `AnansiCore.get_instance()` 单例
2. 调用 `start()` 启动所有 Collector（socket、shared memory、GPU/NPU/NUMA、container 等）
3. 等待初始采集（约 2 秒）
4. 调用 `trigger_collect()` 手动触发采集
5. 调用 `get_last_graph()` 获取结果 Graph
6. 遍历 `graph.nodes` 查看实体，遍历 `graph.edges` 查看关系
7. 调用 `stop()` 清理

**预期结果**：

- 返回的 Graph 包含多个实体（`ProcessEntity`、`SocketEntity`、`SharedMemoryEntity` 等）
- 实体 `global_id` 格式形如 `Process(pid=1234,ppid=5678)`、`Socket(127.0.0.1:18090(TCP))`
- 边表示进程间的通信关系和结构关系

## Step 2: 启动 HTTP 服务

```bash
# 使用默认设置（localhost:18090）
python -m anansi
```

服务启动后：
- API 根目录：`http://localhost:18090`
- Swagger 文档：`http://localhost:18090/docs`

## Step 3: 查询 API

在另一个终端中查询拓扑数据：

```bash
# 获取服务元数据
curl http://localhost:18090/

# 获取最新拓扑图（JSON）
curl http://localhost:18090/graph

# 获取压缩文本摘要
curl http://localhost:18090/compressed_graph

# 查看运行状态
curl http://localhost:18090/status

# 手动触发一次采集
curl -X POST http://localhost:18090/control/trigger
```

**`/status` 响应结构**：

| 字段 | 说明 |
|------|------|
| `env` | 主机元数据（IP、hostname、machine_id） |
| `content.running` | 是否正在采集 |
| `content.graph.node_count` | 实体数量 |
| `content.graph.edge_count` | 边数量 |
| `content.collectors.types` | 活跃的 Collector 类型列表 |
| `content.subscribers.names` | 已注册的 Subscriber 名称列表 |

## Step 4: 自定义配置

创建 JSON 配置文件来定制行为：

```json
{
  "server_config": {
    "server_addr": {"host": "0.0.0.0", "port": 9090},
    "preferred_backend": "FastAPIServer"
  },
  "tmp_dir": "local/run/anansi",
  "collector_config": {
    "disabled_collectors": ["NPUCollector"]
  }
}
```

使用自定义配置运行：

```bash
python -m anansi --config my_config.json
```

## Step 5: 离线批量采集

无需 HTTP 服务，直接采集并输出结果文件：

```bash
# 采集 30 秒
python -m anansi --offline --duration 30
```

输出文件（位于配置的 `tmp_dir` 目录）：
- `topology_graph.json` — 完整的图 JSON
- `topology_graph.txt` — 人类可读的图描述

## Step 6: 监控指定进程

```bash
# 以 PID 1234 为种子节点启动采集
python -m anansi --pid 1234
```

## 常用模式

### 持续监控

```bash
# 后台运行
nohup python -m anansi --config production.json > anansi.log 2>&1 &
```

### 自定义 Subscriber

继承 `GraphSubscriber` 实现 `_on_recv(graph)` 方法，在每次采集后自动处理更新的图数据。可通过 HTTP API `POST /subscriber` 动态注册，或编程式添加到 `SubscriberCollection`。

### Python 客户端

通过 `requests` 库调用 REST API：
- `GET /graph` 获取拓扑数据
- `POST /control/trigger` 触发采集
- `GET /status` 监控运行状态

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 图为空 | 确保有网络/IPC 流量、检查权限、等待首次采集（5-10 秒） |
| HTTP 服务无法启动 | `uv sync --group server` 安装 FastAPI/Uvicorn |
| 端口被占用 | `python -m anansi --port 9090` |

## 相关文档

- **[Configuration Guide](../configuration.md)**：Collector 和服务配置
- **[Backend API Reference](../backend/api.md)**：完整 API 文档
- **[Architecture Overview](../architecture/overview.md)**：系统设计
- **[Running Anansi](../user-guide/running.md)**：完整运行指南

## Tips

- **调试**：使用 `--log-level DEBUG` 启用详细日志
- **性能**：通过 Subscriber 的 `expected_update_interval` 控制采集频率
- **快速测试**：`--offline --duration 10` 无需启动服务
- **可视化**：使用 `anansi-vis` CLI 导出图为 HTML/DrawIO/GEXF/Graphviz 格式
