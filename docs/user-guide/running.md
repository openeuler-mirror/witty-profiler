# Running Anansi

本指南涵盖 Anansi 的所有运行方式，包括命令行、编程接口和后台部署。

## 命令行接口

### 基本用法

```bash
python -m anansi
# 或
anansi
```

默认以在线模式启动 HTTP 服务，绑定 `0.0.0.0:18090`，启用所有未禁用的 Collector。

### CLI 参数参考

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--config PATH` | str | 无 | 配置文件路径（JSON 格式） |
| `--host HOST` | str | 配置值 | 服务绑定地址（覆盖配置） |
| `--port PORT` | int | 配置值 | 服务绑定端口（覆盖配置） |
| `--offline` | flag | — | 离线模式（无 HTTP 服务） |
| `--duration`, `-d` | float | 10.0 | 离线模式采集时长（秒） |
| `--pid` | int | 无 | 指定监控的目标进程 PID（作为种子节点） |
| `--log-level` | str | 无 | 日志级别：VERBOSE / DEBUG / INFO / REPORT / WARNING / ERROR / CRITICAL |
| `--dump-config`, `--dump` | str | 无 | 导出解析后的配置为 JSON 文件并退出 |
| `--verify` | flag | — | 校验 sniffer 二进制依赖并退出 |
| `--view-graph` | flag | — | 交互式查看压缩后的图 JSON 文件并退出 |

### 常用命令示例

```bash
# 生产环境服务
python -m anansi --config configs/production.json

# 本地开发
python -m anansi --host 127.0.0.1 --port 8000

# 快速离线测试（10 秒）
python -m anansi --offline --duration 10

# 长时间批量采集
python -m anansi --offline --duration 300

# 监控指定进程
python -m anansi --pid 1234

# 导出当前配置
python -m anansi --dump-config local/config.snapshot.json
```

### 进程锁

Anansi 通过进程文件锁（`/tmp/anansi/anansi_instance.lock`）防止并发运行多个实例。锁文件中记录了 PID、运行模式（online/offline）和绑定地址等元数据，报错时会提示当前占用实例的信息。

## 服务模式

### 在线模式（HTTP Server）

**默认行为**：启动 REST API 服务，支持实时查询。

**依赖**：`fastapi` + `uvicorn`（通过 `uv sync --group server` 安装）

**流程**：
1. 启动 AnansiCore（Collector 开始运行）
2. 启动 FastAPI/Uvicorn HTTP 服务
3. 提供 REST API 端点
4. 持续运行直到 Ctrl+C

**访问方式**：
- 浏览器：`http://localhost:18090`
- Swagger UI：`http://localhost:18090/docs`
- CLI：`curl http://localhost:18090/graph`

### 离线模式（Batch Collection）

**用途**：固定时长采集，不启动 HTTP 服务。

```bash
python -m anansi --offline --duration 30
```

**流程**：
1. 启动 AnansiCore 和 Collector
2. 运行指定时长
3. 触发最终采集
4. 输出 `topology_graph.json` 和 `topology_graph.txt` 到配置的 `tmp_dir` 目录
5. 清理退出

**说明**：
- 当 FastAPI 可用时，`FastAPIServer.run_offline()` 写入文件到 `tmp_dir`
- 当 FastAPI 不可用（回退服务器）时，图 JSON 输出到标准输出

**适用场景**：
- 无需服务开销的快速测试
- 批量采集后离线分析
- CI/CD 集成
- 调试 Collector 输出

## 编程接口

### 基本使用

通过 `AnansiCore` 单例进行编程式拓扑采集：

1. 获取 `AnansiCore` 单例实例
2. 调用 `start()` 启动所有 Collector
3. 调用 `trigger_collect()` 手动触发采集
4. 调用 `get_last_graph()` 获取最新图
5. 调用 `stop()` 清理停止

**注意**：`start()` / `stop()` 使用引用计数，支持嵌套调用。只有当计数归零时才真正停止。

### 核心 API

| 方法 | 说明 |
|------|------|
| `AnansiCore.get_instance()` | 获取单例 |
| `start()` | 启动采集（引用计数 +1） |
| `stop()` | 停止采集（引用计数 -1，归零时真正停止） |
| `trigger_collect()` | 手动触发一次采集并通知 Subscriber |
| `trigger_clear()` | 清除采集数据 |
| `get_last_graph()` | 获取缓存的最新 Graph（若无则返回空 Graph） |
| `is_running()` | 检查是否正在运行 |

### Graph 对象操作

获取到的 Graph 对象提供以下能力：

| 操作 | 说明 |
|------|------|
| `graph.nodes` | 实体列表（`list[Entity]`） |
| `graph.edges` | 边列表（`list[Edge]`） |
| `graph.model_dump()` | 序列化为 dict |
| `graph.model_dump_json()` | 序列化为 JSON 字符串 |
| `graph.describe()` | 人类可读的摘要文本 |
| `graph.to_mermaid_text()` | Mermaid 图表文本 |
| `graph1 + graph2` | 合并两个图 |

详细文档见 [Graph Model](../architecture/graph-model.md)。

### 自定义 Subscriber

继承 `GraphSubscriber` 并实现 `_on_recv(graph)` 方法，即可在每次采集后自动收到图更新通知。通过 `SubscriberCollection` 注册自定义 Subscriber。

可用的内置 Subscriber 类型：
- `NaiveMemoryStorageGraphSubscriber` — 内存缓存
- `ConsoleGraphSubscriber` — 控制台输出
- `FileGraphDescSubscriber` — 文件追加写入描述
- `FileJsonGraphSubscriber` — JSON 文件写入
- `HttpPostGraphSubscriber` — HTTP POST 远程推送
- `MongoDBGraphSubscriber` — MongoDB 写入

### 使用特定 Collector

通过 `CollectorSet` 可以组合特定的 Collector 子集进行采集，而不是使用全部默认 Collector。也可以通过配置 `collector_config.disabled_collectors` 排除不需要的 Collector。

## 配置

### 配置文件格式

JSON 格式，配置 dataclass 定义在 `src/anansi/config_manager/configs/` 下。

加载方式：

```bash
python -m anansi --config config.json
```

### 优先级

1. **CLI 参数**（最高优先级）
2. **配置文件**（`--config` 指定）
3. **框架默认值**（dataclass 默认值）

### 环境变量

`ANANSI_ROOT_LOGGER_LEVEL` 可设置根日志级别。

详细配置说明见 [Configuration Guide](../configuration.md)。

## 后台部署

### systemd（Linux）

创建 systemd service 文件，配置 `ExecStart` 指向 `python -m anansi --config /etc/anansi/config.json`，设置 `Restart=on-failure`。

### nohup

```bash
nohup python -m anansi --config config.json > anansi.log 2>&1 &
echo $! > anansi.pid
```

### screen/tmux

在 screen 或 tmux 会话中启动，方便后台运行和日志查看。

### Docker

基于 `python:3.11-slim` 镜像，安装依赖后以 `python -m anansi --config configs/production.json` 作为入口，暴露 18090 端口。

## 监控与健康检查

- **HTTP 健康检查**：`GET /status` 端点返回运行状态、节点/边统计
- **日志**：通过 `--log-level` 或 `ANANSI_ROOT_LOGGER_LEVEL` 控制
  - `VERBOSE` / `DEBUG`：详细的 Collector 事件和图构建过程
  - `INFO`：正常运行（启停、采集触发）
  - `REPORT`：摘要报告级别
  - `WARNING` / `ERROR`：问题和异常

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| `ModuleNotFoundError: No module named 'fastapi'` | `uv sync --group server` |
| 图为空 | 检查 Collector 是否启动、生成网络流量、确保权限、等待首次采集 |
| 端口被占用 | `--port 9090` 或停止占用进程 |
| 进程锁冲突 | 另一个 Anansi 实例正在运行，查看锁文件中的元数据确认 |
| 内存增长 | 调整 `expected_update_interval` 降低采集频率，或 `POST /control/clear` 清理数据 |

## 相关文档

- **[Backend API Reference](../backend/api.md)**：完整的 REST API 文档
- **[Configuration Guide](../configuration.md)**：详细的配置选项说明
- **[Architecture Overview](../architecture/overview.md)**：系统设计与组件
