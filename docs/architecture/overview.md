# Architecture Overview

Anansi 使用分层架构来发现系统拓扑，并通过 HTTP API 和订阅者回调暴露结果。

## 系统架构

```text
┌──────────────────────────────────────────────────────────────────┐
│                      HTTP API Layer                              │
│   FastAPIServer  |  OnlineDisabledServer (fallback)              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────┴─────────────────────────────────────┐
│                    Controller Layer                               │
│   AnansiServer (Singleton) ── 后端选择与生命周期代理              │
│   AnansiCore   (Singleton) ── 采集编排、订阅者通知、后台循环      │
└────────────────────────────┬─────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
┌─────────────┴──────────┐   ┌──────────────┴──────────────────┐
│    Collector Layer      │   │      Subscriber Layer           │
│    CollectorSet         │   │      SubscriberCollection       │
│    (BFS 图扩展)         │   │      (广播通知)                  │
└─────────────┬──────────┘   └─────────────────────────────────┘
              │
┌─────────────┴──────────────────────────────────────────────────┐
│                   Local / Remote Collectors                     │
│  Socket │ SharedMemory │ GPU │ NPU │ NUMA │ RDMA │ Container  │
│  IPC │ CommonParent │ Static │ TopCpuUsage │ Remote            │
└─────────────┬──────────────────────────────────────────────────┘
              │
┌─────────────┴──────────────────────────────────────────────────┐
│                Kernel Instrumentation (eBPF)                    │
│  Socket Sniffer │ Cache Miss Monitor │ Sched Monitor            │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│               Visualization Layer （离线导出）                   │
│  Graph → LayoutGraph → Renderer (HTML/DrawIO/GEXF/Graphviz)    │
└────────────────────────────────────────────────────────────────┘
```

## 拓扑采集原理（High-Level）

Anansi 将拓扑采集抽象为“多源观测 → 图融合 → 持续发布”的流程：

1. **多源观测**：从 socket、共享内存、NUMA、GPU/NPU、容器等不同信号源并行获取系统状态。
2. **种子与扩展**：先由种子采集器生成初始节点，再按实体类型进行邻居扩展，逐步补全关联关系。
3. **统一建模**：将异构观测统一映射为实体（nodes）与关系（edges），形成一致的拓扑语义。
4. **去重与合并**：跨采集器、跨轮次对重复实体与边进行合并，保证图的稳定性与可比较性。
5. **增量发布**：将最新拓扑持续输出给 API 与订阅者，支持在线查询与离线分析。

该设计的核心目标是：在不绑定具体实现细节的前提下，稳定表达系统中“谁与谁发生了何种关系”，并随时间持续更新。

## 核心组件

### Controller 层

#### AnansiCore（ThreadSafeSingleton）

- 管理 Collector 生命周期（`start` / `stop` / `clear`）
- 在后台线程中协调周期性采集
- 维护 SubscriberCollection，在每次采集后通知所有订阅者
- `_running` 为引用计数（支持嵌套 start/stop），当计数归零时才真正停止
- 通过 `NaiveMemoryStorageGraphSubscriber` 缓存最新图，供 `get_last_graph()` 返回

#### AnansiServer（ThreadSafeSingleton）

- 从 `GlobalConfigManager` 读取 `server_config.preferred_backend`
- 使用 `ServerFactory` 选择并创建 HTTP 后端
- 代理 `run_online(addr, port)` 和 `run_offline(duration)` 方法

### Collection 层

#### CollectorSet（组合模式）

聚合多个 Collector，以统一的 BFS 遍历方式扩展图，跨数据源去重实体和边。

- 种子图仅由 `collector_config.seed_graph_collectors` 中列出的 Collector 提供
- `entity_type2collector` 映射实现按实体类型分发邻居查询
- 支持运行时动态添加 Collector

#### Collector 类型

| Collector | 数据源 | 说明 |
|-----------|--------|------|
| `SocketCollector` | TCP/UDP socket 通信 | 依赖 eBPF Socket Sniffer |
| `SharedMemoryCollector` | 共享内存区域 | |
| `GPUCollector` | GPU 设备映射 | NVIDIA GPU 拓扑 |
| `NPUCollector` | NPU 设备映射 | |
| `NumaCollector` | NUMA 拓扑 | CPU/内存亲和 |
| `RDMACollector` | RDMA 队列与统计 | |
| `ContainerCollector` | 容器/Pod 元数据 | |
| `IPCCollector` | 进程间通信 | |
| `CommonProcessParentCollector` | 公共父进程 | 合并进程树 |
| `StaticCollector` | CLI `--pid` 指定的进程 | 手动种子节点 |
| `TopCpuUsageCollector` | CPU 高使用率进程 | |
| `RemoteCollector` | 远端 Anansi 实例 | 带命名空间的远程图合并 |

活跃 Collector 由配置项 `collector_config.disabled_collectors` 控制。

### Graph 层

详见 [Graph Model](graph-model.md)。

核心要点：
- **Graph** 包含 `nodes: list[Entity]` 和 `edges: list[Edge]`
- 构造时自动去重，支持惰性扩展（`try_add_node` / `try_add_edge`）
- 通过 `model_dump()` 序列化为 dict/JSON
- 支持合并（`+`）、子图比较（`<=` / `>=`）等操作
- Global ID 格式：`{类型缩写}({unique_id})` 或 `{类型缩写}(ns={namespace},{unique_id})`

### Edge 层

边建模实体间的关系与数据流，继承体系为：

- `Edge` → `DirectedEdge` / `UndirectedEdge`
  - `DirectedEdge` → `DeployEdge` / `DataStreamEdge` 等分类边
    - 分类边 → `OwnEdge` / `BelongEdge` / `AccessEdge` / `SendToSocketEdge` 等具体实现

详见 [Graph Model — 边类型](graph-model.md#边类型)。

### Subscriber 层

Subscriber 通过 `SubscriberCollection` 接收图更新通知。

| Subscriber | 用途 |
|------------|------|
| `NaiveMemoryStorageGraphSubscriber` | 内存缓存最新图（`get_last_graph()` 的数据源） |
| `ConsoleGraphSubscriber` | 控制台日志输出 |
| `FileGraphDescSubscriber` | 写入 `graph.describe()` 到文件 |
| `FileJsonGraphSubscriber` | 写入 JSON 图到文件 |
| `HttpPostGraphSubscriber` | POST 图 JSON 到远程 URL |
| `MongoDBGraphSubscriber` | 写入 MongoDB（条件依赖 pymongo） |

- `SubscriberCollection` 的 `expected_next_update_interval` 取所有子订阅者中的最小值
- 支持同步和异步通知模式
- 通过 `SubscriberMeta` 元类自动注册，可通过 HTTP API 动态管理

### Backend 层

| 后端 | 说明 |
|------|------|
| `FastAPIServer` | REST API，提供 Swagger UI，依赖 fastapi + uvicorn |
| `OnlineDisabledServer` | 仅支持离线模式的回退后端 |

- `ServerFactory` 按优先级选择后端：配置指定 > FastAPIServer > 第一个注册的回退
- `ServerMeta` 元类自动注册 Server 子类

### Visualization 层

离线图导出的两阶段流水线：

1. **Layout**：`LayoutFactory.create_layout_from_graph()` 将 Graph 转为 LayoutGraph（层次化布局树）
2. **Renderer**：将 LayoutGraph 渲染为目标格式：HTML / DrawIO / GEXF / PyVis / Graphviz（.svg + .png）

- 支持多种布局引擎（`default` / `constraint` / `gephi`），通过 `--layout-engine` 参数或 API 选择
- `LayoutRendererMeta` 元类自动注册渲染器，支持扩展新输出格式
- CLI 入口：`anansi-vis`

### Configuration 层

配置由 `GlobalConfigManager`（Singleton）管理，加载优先级：

1. **CLI 参数**（最高优先级）
2. **配置文件**（`--config path.json`）
3. **框架默认值**（dataclass 默认值）

配置 dataclass 定义在 [src/anansi/config_manager/configs](../../src/anansi/config_manager/configs)，详见 [Configuration Guide](../configuration.md)。
