# Updates

* [2026-03-05] README 精简为必要信息入口页
  - 保留最小安装、构建、运行与配置要点
  - 删除重复的 API/架构细节与长示例代码，统一下沉到 docs
  - 补充 high-level 拓扑采集原理入口链接

* [2026-03-05] 文档新增“拓扑采集原理（High-Level）”简述
  - 在 `docs/architecture/overview.md` 增加高层原理说明，覆盖多源观测、种子扩展、统一建模、去重合并、增量发布
  - 在 `docs/monitoring/overview.md` 增加跳转链接，引导读者查看架构层说明

* [2026-02-24] 添加了NVIDIA GPU监控功能，与NPU监控功能对采集齐
  - 扩展了GPUEntity实体，添加了pci_bus_id、id、cpu_affinity、numa_affinity属性
  - 创建了GPUDeploymentManager，用于解析GPU与CPU/NUMA的亲和性关系
  - 创建了GPUAccessSniffer抽象基类和NVIDIAGPUAccessSniffer实现，用于采集GPU设备信息和进程映射
  - 创建了GPUCollector，用于构建GPU拓扑图
  - 添加了GPUSnifferConfig配置类
  - 更新了文档，添加了GPU监控指标说明
  - 更新了架构文档，添加了GPUCollector说明
  - 更新了collector配置，将GPUCollector添加到种子图收集器列表中
