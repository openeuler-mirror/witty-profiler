# Anansi HTTP Server Documentation

> **此文档已合并到 [Backend API Reference](backend/api.md)**，请前往查阅完整的 REST API 文档。

概要：

- Anansi HTTP 服务通过 `FastAPIServer` 暴露 REST 端点，用于拓扑采集与查询
- 支持在线模式（FastAPI）和离线模式（批量采集）
- 所有 JSON 端点返回 `{"env": {...}, "content": {...}}` 统一信封格式
- 详细端点列表、请求/响应说明、CLI 参数和配置见 **[Backend API Reference](backend/api.md)**
