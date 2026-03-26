# Project File Map

本文档列出项目中的关键文件和目录，便于文档内快速导航。

## 核心入口

| 文件 | 说明 |
|------|------|
| [src/witty_profiler/\_\_main\_\_.py](../src/witty_profiler/__main__.py) | CLI 入口（`witty-profiler` 命令） |
| [src/witty_profiler/controller/witty_profiler_core.py](../src/witty_profiler/controller/witty_profiler_core.py) | 核心编排器（WittyProfilerCore） |
| [src/witty_profiler/backend/witty_profiler.py](../src/witty_profiler/backend/witty_profiler.py) | 服务控制器（WittyProfilerServer） |
| [src/witty_profiler/backend/fastapi_server.py](../src/witty_profiler/backend/fastapi_server.py) | FastAPI REST API |
| [src/witty_profiler/backend/default_server.py](../src/witty_profiler/backend/default_server.py) | 离线回退服务 |
| [src/witty_profiler/backend/base.py](../src/witty_profiler/backend/base.py) | Server 基类与工厂 |

## 图模型

| 文件/目录 | 说明 |
|-----------|------|
| [src/witty_profiler/graph/graph.py](../src/witty_profiler/graph/graph.py) | Graph 数据类 |
| [src/witty_profiler/entity/entity_base.py](../src/witty_profiler/entity/entity_base.py) | Entity 基类与工厂 |
| [src/witty_profiler/entity/entity_namespace.py](../src/witty_profiler/entity/entity_namespace.py) | 命名空间管理 |
| [src/witty_profiler/entity/node_entity/](../src/witty_profiler/entity/node_entity/) | 所有实体类型定义 |
| [src/witty_profiler/edge/edge.py](../src/witty_profiler/edge/edge.py) | Edge 基类、DirectedEdge、UndirectedEdge |
| [src/witty_profiler/edge/edge_category.py](../src/witty_profiler/edge/edge_category.py) | 边分类体系 |
| [src/witty_profiler/edge/structual/](../src/witty_profiler/edge/structual/) | 结构边（Own/Belong/Access 等） |
| [src/witty_profiler/edge/socket/](../src/witty_profiler/edge/socket/) | Socket 数据流边 |
| [src/witty_profiler/edge/cpu/](../src/witty_profiler/edge/cpu/) | NUMA 亲和边 |
| [src/witty_profiler/edge/ipc/](../src/witty_profiler/edge/ipc/) | IPC 边 |
| [src/witty_profiler/edge/rdma/](../src/witty_profiler/edge/rdma/) | RDMA 相关边与嗅探器 |
| [src/witty_profiler/edge/xpu/](../src/witty_profiler/edge/xpu/) | GPU/NPU 部署边 |
| [src/witty_profiler/edge/docker/](../src/witty_profiler/edge/docker/) | 容器边 |

## 采集器

| 文件/目录 | 说明 |
|-----------|------|
| [src/witty_profiler/collector/collector_base.py](../src/witty_profiler/collector/collector_base.py) | Collector 基类（BFS 图扩展） |
| [src/witty_profiler/collector/collect_set.py](../src/witty_profiler/collector/collect_set.py) | CollectorSet 组合模式 |
| [src/witty_profiler/collector/local_collector/](../src/witty_profiler/collector/local_collector/) | 本地 Collector 实现 |
| [src/witty_profiler/collector/remote_collector/](../src/witty_profiler/collector/remote_collector/) | 远程 Collector 实现 |

## 订阅者

| 文件/目录 | 说明 |
|-----------|------|
| [src/witty_profiler/subscriber/subscriber_base.py](../src/witty_profiler/subscriber/subscriber_base.py) | Subscriber 基类 |
| [src/witty_profiler/subscriber/subscriber_collection.py](../src/witty_profiler/subscriber/subscriber_collection.py) | SubscriberCollection 组合模式 |
| [src/witty_profiler/subscriber/implementations/](../src/witty_profiler/subscriber/implementations/) | 内置 Subscriber 实现 |

## 配置

| 文件/目录 | 说明 |
|-----------|------|
| [src/witty_profiler/config_manager/config_manager.py](../src/witty_profiler/config_manager/config_manager.py) | GlobalConfigManager |
| [src/witty_profiler/config_manager/configs/](../src/witty_profiler/config_manager/configs/) | 配置 dataclass 定义 |
| [configs/config.sample.json](../configs/config.sample.json) | 配置文件示例 |

## 公共模块

| 文件 | 说明 |
|------|------|
| [src/witty_profiler/common/constants.py](../src/witty_profiler/common/constants.py) | 全局常量 |
| [src/witty_profiler/common/env_manager.py](../src/witty_profiler/common/env_manager.py) | 环境信息管理 |
| [src/witty_profiler/common/id_manager.py](../src/witty_profiler/common/id_manager.py) | Global ID 管理器 |
| [src/witty_profiler/common/logging.py](../src/witty_profiler/common/logging.py) | 日志系统 |
| [src/witty_profiler/common/process_lock.py](../src/witty_profiler/common/process_lock.py) | 进程文件锁 |
| [src/witty_profiler/common/singleton.py](../src/witty_profiler/common/singleton.py) | 单例模式基类 |

## 可视化

| 文件/目录 | 说明 |
|-----------|------|
| [src/witty_profiler/visualize/vis.py](../src/witty_profiler/visualize/vis.py) | 可视化入口（`witty-profiler-vis` CLI） |
| [src/witty_profiler/visualize/layout/](../src/witty_profiler/visualize/layout/) | 布局引擎 |
| [src/witty_profiler/visualize/renderer/](../src/witty_profiler/visualize/renderer/) | 渲染器（HTML/DrawIO/GEXF/Graphviz） |

## eBPF 工具

| 文件/目录 | 说明 |
|-----------|------|
| [src/witty_profiler/tools/ebpftools/](../src/witty_profiler/tools/ebpftools/) | CMake 构建的 eBPF 工具源码 |
| [src/witty_profiler/tools/build.py](../src/witty_profiler/tools/build.py) | 构建脚本（`witty-profiler-build`） |
| [src/witty_profiler/binary/](../src/witty_profiler/binary/) | 编译产物输出路径 |

## 存储

| 文件 | 说明 |
|------|------|
| [src/witty_profiler/storage/rotated_file_storage.py](../src/witty_profiler/storage/rotated_file_storage.py) | 轮转文件存储 |

## 文档

| 文件 | 说明 |
|------|------|
| [docs/index.md](index.md) | 文档首页 |
| [docs/architecture/overview.md](architecture/overview.md) | 架构总览 |
| [docs/architecture/graph-model.md](architecture/graph-model.md) | 图模型 |
| [docs/backend/api.md](backend/api.md) | HTTP API 参考 |
| [docs/configuration.md](configuration.md) | 配置指南 |
| [docs/user-guide/running.md](user-guide/running.md) | 运行指南 |
| [docs/monitoring/overview.md](monitoring/overview.md) | 监控概览 |
| [docs/profiler/](profiler/) | eBPF profiler 使用指南 |

## 测试

| 目录 | 说明 |
|------|------|
| [tests/](../tests/) | 测试根目录 |
| [tests/test_backend/](../tests/test_backend/) | 后端测试 |
| [tests/test_collector/](../tests/test_collector/) | 采集器测试 |
| [tests/test_graph/](../tests/test_graph/) | 图模型与可视化测试 |
| [tests/test_controller/](../tests/test_controller/) | 控制器测试 |
| [tests/test_edge/](../tests/test_edge/) | 边测试 |
| [tests/test_subscriber/](../tests/test_subscriber/) | 订阅者测试 |
