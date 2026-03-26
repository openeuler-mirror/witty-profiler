# Skill Authoring SOP

## Scope
This SOP captures the standard workflow for authoring and maintaining skills in this repository.

## Workflow
1. Clarify the skill objective, inputs, and outputs.
2. Draft a concise SKILL document that explains the core approach and operating modes.
3. Extract long or detailed explanations into reference notes and link them from the SKILL document.
4. Store static assets and configuration templates as resources and reference them from the SKILL document.
5. Provide helper scripts for common operational tasks (environment checks, run modes, data retrieval).
6. Review the skill package for completeness, consistency, and broken links.

## Maintenance
- Keep skill materials aligned with upstream API and configuration changes.
- Update references and resources together when behavior or contracts change.
- Ensure scripts remain minimal, self-describing, and safe to execute.
- When adding low-level profilers, document build prerequisites, kernel header generation, and lifecycle steps for attaching/detaching perf-event probes.
- For each new profiler tool, add a usage guide under `docs/profiler/` to capture build, run, and output format expectations.
- Prefer optional filter flags with sensible defaults (e.g., missing pid/tid/cpu implies full collection) and document the default behavior explicitly.
- When a profiler groups metrics, document the grouping key order and keep the CLI output aligned to that order.
- If a profiler uses main/standby maps for periodic output, document the switching interval and whether maps are cleared after each window.
- When using fixed-size BPF maps, expose per-window drop counts to surface saturation and data loss.
- For perf-event based profilers, provide a configurable sample period to mitigate kernel throttling.
- For long-running sniffer monitors, include a process lock, buffered reads, and binary compatibility checks via `-v` outputs.
- For resource-heavy CLIs, enforce a single-instance process lock before initializing collectors or backends, and emit a clear user-facing message when the lock is held.
- When using process locks, write pid and runtime mode details into the lock file so users can identify the running instance.
- For scheduler monitors, use sched_switch for accounting and finish_task_switch to capture the next task start timestamp.
- When diagnosing singleton duplication, verify module identity and import paths first (ensure a single package root on `sys.path` and avoid mixed editable installs with extra source roots).
- For HTTP API changes, update route listings and response descriptions across documentation and ensure response envelope exceptions are explicitly called out.
- If consolidating ebpftools `vmlinux.h` files, use a shared per-arch directory (for example, src/anansi/tools/ebpftools/vmlinux/<arch>) referenced by all CMakeLists.txt and remember `vmlinux.h` is kernel/BTF-specific, so do not reuse across incompatible kernels.
- When refreshing documentation, verify CLI flags against `src/anansi/__main__.py`, verify API envelopes against `src/anansi/backend/fastapi_server.py`, and ensure doc links reflect existing files.
- For documentation layering, place implementation-agnostic design principles in `docs/architecture/` and keep `docs/monitoring/` focused on observable entities, edges, and metrics with cross-links instead of duplicated theory.
- When testing CollectorSet seed graphs, mock `GlobalConfigManager` and include test collector class names in `collector_config.seed_graph_collectors`; `_get_seed_graph` logs and skips exceptions instead of raising.
- For graph visualization features, standardize on a layered architecture (`Graph -> Layout -> Renderer`) so new export formats can be added without changing graph domain models.
- For hierarchical topology rendering, derive parent-child relationships from explicit structural edges first, then use entity embedded references as fallback.
- For layout engines that must emit node geometry, prefer a stable three-step pipeline: recursive relative slot assignment, bottom-up size computation, and top-down absolute coordinate propagation.
- Keep geometry units in layout-space (for example, grid units) and let renderers perform unit scaling (for example, grid-to-pixel), so layout algorithms stay renderer-agnostic.

