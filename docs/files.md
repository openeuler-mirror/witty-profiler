# Project File Map

本文档列出项目中的关键文件和目录，便于文档内快速导航。

## 核心入口

| 文件 | 说明 |
|------|------|
| [src/anansi/\_\_main\_\_.py](../src/anansi/__main__.py) | CLI 入口（`anansi` 命令） |
| [src/anansi/controller/anansi_core.py](../src/anansi/controller/anansi_core.py) | 核心编排器（AnansiCore） |
| [src/anansi/backend/anansi.py](../src/anansi/backend/anansi.py) | 服务控制器（AnansiServer） |
| [src/anansi/backend/fastapi_server.py](../src/anansi/backend/fastapi_server.py) | FastAPI REST API |
| [src/anansi/backend/default_server.py](../src/anansi/backend/default_server.py) | 离线回退服务 |
| [src/anansi/backend/base.py](../src/anansi/backend/base.py) | Server 基类与工厂 |

## 图模型

| 文件/目录 | 说明 |
|-----------|------|
| [src/anansi/graph/graph.py](../src/anansi/graph/graph.py) | Graph 数据类 |
| [src/anansi/entity/entity_base.py](../src/anansi/entity/entity_base.py) | Entity 基类与工厂 |
| [src/anansi/entity/entity_namespace.py](../src/anansi/entity/entity_namespace.py) | 命名空间管理 |
| [src/anansi/entity/node_entity/](../src/anansi/entity/node_entity/) | 所有实体类型定义 |
| [src/anansi/edge/edge.py](../src/anansi/edge/edge.py) | Edge 基类、DirectedEdge、UndirectedEdge |
| [src/anansi/edge/edge_category.py](../src/anansi/edge/edge_category.py) | 边分类体系 |
| [src/anansi/edge/structual/](../src/anansi/edge/structual/) | 结构边（Own/Belong/Access 等） |
| [src/anansi/edge/socket/](../src/anansi/edge/socket/) | Socket 数据流边 |
| [src/anansi/edge/cpu/](../src/anansi/edge/cpu/) | NUMA 亲和边 |
| [src/anansi/edge/ipc/](../src/anansi/edge/ipc/) | IPC 边 |
| [src/anansi/edge/rdma/](../src/anansi/edge/rdma/) | RDMA 相关边与嗅探器 |
| [src/anansi/edge/xpu/](../src/anansi/edge/xpu/) | GPU/NPU 部署边 |
| [src/anansi/edge/docker/](../src/anansi/edge/docker/) | 容器边 |

## 采集器

| 文件/目录 | 说明 |
|-----------|------|
| [src/anansi/collector/collector_base.py](../src/anansi/collector/collector_base.py) | Collector 基类（BFS 图扩展） |
| [src/anansi/collector/collect_set.py](../src/anansi/collector/collect_set.py) | CollectorSet 组合模式 |
| [src/anansi/collector/local_collector/](../src/anansi/collector/local_collector/) | 本地 Collector 实现 |
| [src/anansi/collector/remote_collector/](../src/anansi/collector/remote_collector/) | 远程 Collector 实现 |

## 订阅者

| 文件/目录 | 说明 |
|-----------|------|
| [src/anansi/subscriber/subscriber_base.py](../src/anansi/subscriber/subscriber_base.py) | Subscriber 基类 |
| [src/anansi/subscriber/subscriber_collection.py](../src/anansi/subscriber/subscriber_collection.py) | SubscriberCollection 组合模式 |
| [src/anansi/subscriber/implementations/](../src/anansi/subscriber/implementations/) | 内置 Subscriber 实现 |

## 配置

| 文件/目录 | 说明 |
|-----------|------|
| [src/anansi/config_manager/config_manager.py](../src/anansi/config_manager/config_manager.py) | GlobalConfigManager |
| [src/anansi/config_manager/configs/](../src/anansi/config_manager/configs/) | 配置 dataclass 定义 |
| [configs/config.sample.json](../configs/config.sample.json) | 配置文件示例 |

## 公共模块

| 文件 | 说明 |
|------|------|
| [src/anansi/common/constants.py](../src/anansi/common/constants.py) | 全局常量 |
| [src/anansi/common/env_manager.py](../src/anansi/common/env_manager.py) | 环境信息管理 |
| [src/anansi/common/id_manager.py](../src/anansi/common/id_manager.py) | Global ID 管理器 |
| [src/anansi/common/logging.py](../src/anansi/common/logging.py) | 日志系统 |
| [src/anansi/common/process_lock.py](../src/anansi/common/process_lock.py) | 进程文件锁 |
| [src/anansi/common/singleton.py](../src/anansi/common/singleton.py) | 单例模式基类 |

## 可视化

| 文件/目录 | 说明 |
|-----------|------|
| [src/anansi/visualize/vis.py](../src/anansi/visualize/vis.py) | 可视化入口（`anansi-vis` CLI） |
| [src/anansi/visualize/layout/](../src/anansi/visualize/layout/) | 布局引擎 |
| [src/anansi/visualize/renderer/](../src/anansi/visualize/renderer/) | 渲染器（HTML/DrawIO/GEXF/Graphviz） |

## eBPF 工具

| 文件/目录 | 说明 |
|-----------|------|
| [src/anansi/tools/ebpftools/](../src/anansi/tools/ebpftools/) | CMake 构建的 eBPF 工具源码 |
| [src/anansi/tools/build.py](../src/anansi/tools/build.py) | 构建脚本（`anansi-build`） |
| [src/anansi/binary/](../src/anansi/binary/) | 编译产物输出路径 |

## 存储

| 文件 | 说明 |
|------|------|
| [src/anansi/storage/rotated_file_storage.py](../src/anansi/storage/rotated_file_storage.py) | 轮转文件存储 |

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
