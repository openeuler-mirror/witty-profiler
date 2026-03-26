# Project Progress

## 2026-01-29
- Completed skill documentation and assets for topology perception under skill/witty-profiler-topolody-perception-skill.
- Added Linux shell scripts for environment checks, online/offline runs, and graph retrieval.
- Added reference notes and sample resource payloads for API usage.

## 2026-01-30
- Investigated repeated `GlobalConfigManager` initialization during CLI runs; identified import-path duplication and non-thread-safe singleton as primary suspects.

## 2026-02-03
- Added a compressed graph HTTP endpoint that returns the plain-text graph summary and updated API documentation to reflect the new route.
- Updated the RESTful backend client and interactive API client to support `/compressed_graph`.


## 2026-02-04
- Added a libbpf-based cache miss monitor that attaches to hardware perf events and counts cache misses for a specific pid/tid/cpu over a time window.
- Documented cache miss profiler usage under docs/profiler.

## 2026-02-05
- Updated cache miss monitor to allow optional pid/tid/cpu filters and attach perf events across all CPUs by default.
- Switched cache miss aggregation to group by (cpu, pid, tid) and dump per-group counts.
- Added fixed-size dual-map switching, interval-based output, and csv/msgspec selection for cache miss monitoring.
- Added per-window drop counters to surface map saturation during cache miss collection.
- Added window re-arming and CSV flush to avoid stalls and buffered output gaps.
- Added configurable perf sample period to reduce throttling-induced stalls.
- Implemented CacheMonitor service mirroring SocketMonitor for cache miss collection output.
- Switched cache miss metrics to L1I/LLC with total aggregation and (cpu,tgid,pid) grouping.
- Added cache sniffer retention window trimming based on cache monitor timestamps.
- Added cache sniffer aggregation to merge records by cpu/tgid/pid with summed counts and min/max window times.
- Added sched_monitor_c eBPF tool with dual-map switching and CSV/msgspec output.
- Documented sched monitor usage under docs/profiler.
- Updated sched monitor to track per-CPU running thread via sched_switch only, outputting pid/tgid/cpu/time.
- Added Python sched monitor service mirroring cache monitor for sched output ingestion.
- Added sched sniffer wrapper for buffered sched runtime data consumption.
- Added sched monitor window timestamps and time-window trimming for output records.
- Reviewed ebpftools CMake vmlinux.h generation logic and noted consolidation options (shared arch directory or symlink) while keeping kernel-specific constraints.
- Pointed ebpftools CMake vmlinux.h lookup to shared src/witty_profiler/tools/ebpftools/vmlinux/<arch> path.

## Next Steps
- Validate scripts in a real runtime environment with active communication workloads.
- Confirm resource config paths align with deployment layout (especially socket sniffer binary path).
- Verify runtime `sys.path` and module origin to ensure `witty_profiler` is imported from a single package root when using the CLI.

## 2026-02-06
- Refreshed documentation to align with current CLI flags, config schema, API response envelope, and offline output behavior.
- Updated profiler guides to use shared ebpftools vmlinux path and the `witty-profiler-build` workflow.
- Cleaned up outdated doc links and examples to match current repository structure.
- Updated collector/controller/graph unit tests to reflect CollectorSet seed filtering, Edge/Graph APIs, and ProcessEntity ID changes.
- Fixed remaining unit tests by importing backend modules for patching and resetting GlobalIDManager between entity tests.

## 2026-02-07
- Added a CLI-level process lock to prevent concurrent Witty Profiler runs and surface a clear error when another instance is active.
- Enhanced the CLI process lock to persist pid/mode/host/port metadata and report it in the lock error message.

## 2026-03-03
- Added a new visualization architecture under `src/witty_profiler/visualize/` using a two-stage pipeline: `Graph -> LayoutGraph -> Renderer`.
- Implemented renderer outputs for `html`, `drawio`, `gexf`, `pyvis`, and `graphviz`.
- Enabled nested container layout for hierarchy-style visualization (container/process/thread/socket) using structural edges plus entity fallback fields.
- Set Graphviz export to always generate both `.svg` and `.png` artifacts in one call.
- Added visualization unit tests in `tests/test_graph/test_visualize.py`; verified in uv venv with `2 passed, 1 skipped`.
- Integrated offline backend export in `FastAPIServer.run_offline` to emit `html/drawio/gexf` and `graphviz(.svg+.png)` alongside existing json/txt outputs.
- Added backend tests in `tests/test_backend/test_fastapi_server.py` to verify per-format export calls and failure isolation.

## 2026-03-05
- Implemented pending `DefaultLayout` geometry TODOs: bottom-up size aggregation and top-down absolute coordinate allocation.
- Added recursive relative placement for every deploy container (not only root), enabling full-tree layout geometry generation.
- Added grid-unit geometry fields to `LayoutElement` (`x/y/w/h`) and child local offset caching.
- Updated default renderer structural output to include geometry (`x/y/w/h`) for each layout node.
- Added tests in `tests/test_graph/test_visualize_layout.py` to validate geometry presence, containment constraints, and renderer geometry output.
- Added `html` and `drawio` renderers under `src/witty_profiler/visualize/renderer/` that consume layout geometry and generate SVG-based HTML and draw.io `mxfile` XML outputs.
- Updated renderer registry to support canonical names (`default/html/drawio`) for CLI `-of` selection while keeping class-name lookup compatibility.
