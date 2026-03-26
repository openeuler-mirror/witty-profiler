# 安装 Witty Profiler

> **完整安装指南请参见 [Getting Started — Installation](getting-started/installation.md)**

快速安装：

```bash
uv venv .venv --python 3.11
uv sync                         # 核心依赖
uv sync --group server           # 可选：HTTP 服务端依赖
```

构建 eBPF 工具（可选）：

```bash
witty-profiler-build
```
