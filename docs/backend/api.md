# Anansi Backend API (FastAPI)

`FastAPIServer` 提供的完整 REST 接口。当 `fastapi` 和 `uvicorn` 未安装时，回退到仅支持离线模式的 `OnlineDisabledServer`。

## 前置条件

- 安装服务端依赖：`uv sync --group server`（或 `pip install fastapi uvicorn`）
- 默认绑定地址 `0.0.0.0:18090`（可通过配置或 CLI 覆盖）

## Response Envelope

所有 JSON 端点返回统一的信封格式：

```json
{
 "env": {
  "local_ip": "...",
  "hostname": "...",
  "machine_id": "..."
 },
 "content": { }
}
```

- `env` 来自 `EnvManager`，包含主机元数据（自动检测）
- `content` 包含端点特定数据
- 404 请求被重定向到 `/help`（307）

## 运行服务器

| 模式 | 命令 | 说明 |
|------|------|------|
| 在线模式（默认） | `python -m anansi` | 启动 HTTP 服务 |
| 自定义绑定 | `python -m anansi --host 127.0.0.1 --port 9090` | 覆盖地址端口 |
| 离线批量采集 | `python -m anansi --offline --duration 30` | 无 HTTP 服务，采集后输出文件 |

- 在线模式下，Swagger UI 位于 `http://localhost:18090/docs`
- 离线模式输出 `topology_graph.json` 和 `topology_graph.txt` 到配置的 `tmp_dir` 目录

## 端点一览

### 信息类

| 方法 | 路由 | 返回类型 | 说明 |
|------|------|---------|------|
| GET | `/` | JSON envelope | API 索引、服务元数据、路由列表 |
| GET | `/help` | 纯文本 | 端点列表（CLI 友好） |

### 图数据

| 方法 | 路由 | 返回类型 | 说明 |
|------|------|---------|------|
| GET | `/graph` | JSON envelope | 最新拓扑图（nodes 为实体列表，edges 为边列表） |
| GET | `/compressed_graph` | 纯文本 | `graph.describe()` 的人类可读摘要 |

`/graph` 返回的 `content` 结构：
- `nodes` — 实体对象数组
- `edges` — 边对象数组（**注意：是扁平列表，非邻接表**）

### 状态

| 方法 | 路由 | 返回类型 | 说明 |
|------|------|---------|------|
| GET | `/status` | JSON envelope | 运行状态、节点/边统计、Collector 类型、Subscriber 名称 |

`/status` 返回的 `content` 包含：

| 字段 | 说明 |
|------|------|
| `running` | 是否正在采集 |
| `graph.node_count` | 节点数量 |
| `graph.edge_count` | 边数量（边列表长度） |
| `collectors.count` / `collectors.types` | 活跃的 Collector 数量与类型列表 |
| `subscribers.count` / `subscribers.names` | 注册的 Subscriber 数量与名称列表 |

### 控制

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/control/start` | 启动采集循环（幂等） |
| POST | `/control/stop` | 停止采集 |
| POST | `/control/trigger` | 手动触发一次采集，返回结果图摘要 |
| POST | `/control/clear` | 清除已采集数据 |

成功时返回 `{"status": "success", "message": "..."}` 形式的 content。错误以 HTTP 500 + `detail` 描述。

### Subscriber 管理

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/subscriber` | 注册订阅者（JSON body 包含 `subscriber_type`、可选 `name`、`expected_update_interval`、`async_notify`） |
| DELETE | `/subscriber/{name}` | 按名称注销订阅者（404 若不存在） |
| GET | `/subscribers` | 列出已注册订阅者及可用类型 |

`GET /subscribers` 返回的 content 包含 `count`、`subscribers` 列表（含 name/type/interval）和 `available_types`。

## CLI 参数与配置

重要 CLI 参数（覆盖配置文件设置）：

| 参数 | 说明 |
|------|------|
| `--host` / `--port` | 覆盖 `server_config.server_addr` |
| `--config` | 加载 JSON 配置文件 |
| `--offline` / `--duration` | 离线批量模式（默认时长 10.0 秒） |
| `--pid` | 监控指定进程 PID |
| `--log-level` | 日志级别（VERBOSE / DEBUG / INFO / REPORT / WARNING / ERROR / CRITICAL） |
| `--dump-config` | 导出解析后的配置为 JSON 并退出 |
| `--verify` | 校验 sniffer 二进制并退出 |
| `--view-graph` | 交互式查看压缩后的图文件并退出 |

详细配置说明参见 [Configuration Guide](../configuration.md)。

## 开发说明

- 添加或更新端点：修改 [src/anansi/backend/fastapi_server.py](../../src/anansi/backend/fastapi_server.py)
- 测试：[tests/test_backend](../../tests/test_backend)
- 进程锁确保同一时间只有一个 Anansi 实例运行

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 缺少依赖 | `uv sync --group server` 安装 FastAPI/Uvicorn |
| 端口被占用 | 使用 `--port` 指定其他端口或停止占用进程 |
| 图为空 | 生成网络流量、确保足够权限、等待首次采集完成 |

## License

Apache-2.0
