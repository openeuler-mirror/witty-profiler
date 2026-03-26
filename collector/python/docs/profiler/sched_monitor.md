# **Sched Monitor (eBPF) 使用指南**

## 功能

- 基于 `sched_switch` 统计线程在 CPU 上的运行时间。
- 按 `(pid, tgid, cpu)` 聚合，输出 `time`（纳秒）。
- 每次窗口输出会附带 `window_start_ns` 与 `window_end_ns`。
- 支持 CSV / msgspec 输出格式。
- 主备表双缓冲切换，按固定间隔导出统计结果。

## 目录结构

- 用户态加载器：`src/witty_profiler/tools/ebpftools/sched_monitor_c/main.cpp`
- eBPF 源：`src/witty_profiler/tools/ebpftools/sched_monitor_c/ebpf/sched_monitor.bpf.c`
- 输出逻辑：`src/witty_profiler/tools/ebpftools/sched_monitor_c/dump/`
- 构建脚本：`src/witty_profiler/tools/ebpftools/sched_monitor_c/CMakeLists.txt`

## 环境要求

- Linux 内核支持 eBPF/BTF（常见 5.x+），需 root 运行；Windows 无法直接使用。
- 依赖：`clang`、`llvm`、`libbpf-dev`、`pkg-config`、`zlib1g-dev`、`libelf-dev`、`cmake`、`bpftool`。

```bash
# debian & ubuntu
apt install -y clang llvm libbpf-dev pkg-config zlib1g-dev libelf-dev cmake bpftool
# centos & redhat & openEuler & EulerOS
yum install -y clang llvm libbpf-devel pkgconfig zlib-devel elfutils-libelf-devel cmake bpftool
```

- **vmlinux.h 生成（BTF 必须）**：CMake 会自动检测并生成架构相关的 `vmlinux.h`：
  - **自动生成**：若 `src/witty_profiler/tools/ebpftools/vmlinux/<arch>/vmlinux.h` 不存在，CMake 会在配置阶段自动调用 `bpftool btf dump` 生成
  - **手动生成**（如自动生成失败）：

```bash
# x86_64
bpftool btf dump file /sys/kernel/btf/vmlinux format c > src/witty_profiler/tools/ebpftools/vmlinux/x86_64/vmlinux.h

# aarch64
bpftool btf dump file /sys/kernel/btf/vmlinux format c > src/witty_profiler/tools/ebpftools/vmlinux/aarch64/vmlinux.h
```

## 编译

```bash
# 推荐：使用构建脚本
witty-profiler-build
# 或
python -m witty_profiler.tools.build

# 手动构建（sched_monitor）
cmake -B src/witty_profiler/binary/cpu_sched -S src/witty_profiler/tools/ebpftools/sched_monitor_c -DSCHED_OUTPUT_MSGSPEC=OFF
cmake --build src/witty_profiler/binary/cpu_sched
```

### 输出格式选择

- `-DSCHED_OUTPUT_MSGSPEC=OFF`（默认）：CSV
- `-DSCHED_OUTPUT_MSGSPEC=ON`：msgspec（长度前缀 MessagePack）

## 运行

```bash
sudo src/witty_profiler/binary/cpu_sched/sched_monitor [-v] [-t <TID...>] [-p <TGID...>] [-cpu <CPU...>] [-i <SECONDS>] [-d <SECONDS>] [-m <MAX_ENTRY>] [-o <BPF_OBJ>]
```

### 参数说明

- `-t <tid...>`：线程 PID（TID）列表；缺省表示全部线程。
- `-p <tgid...>`：进程 TGID（进程号）列表；缺省表示全部进程。
- `-cpu <cpu...>`：CPU 核心 ID 列表；缺省表示全部 CPU。
- `-i <seconds>`：统计窗口切换间隔，默认 2 秒。
- `-d <seconds>`：总采样时长，默认 0 表示持续运行直到退出。
- `-m <max_entry>`：统计表最大条目数（主备表与过滤表共用上限）。
- `-o <path>`：BPF 对象文件路径，默认 `sched_monitor_bpf.o`。
- `-v`：输出当前二进制的输出格式并退出。

示例：

```bash
sched_monitor -t 1234 234 -p 234 -cpu 1
sched_monitor -t 1234 234 -p 234 22 -cpu 1 2 4
```

## 输出格式

### CSV

```text
pid,tgid,cpu,time,window_start_ns,window_end_ns
```

### msgspec

- 输出为 **长度前缀（4 字节大端）+ MessagePack 数组**。
- 数组字段顺序：`[pid, tgid, cpu, time]`，窗口时间戳由用户态追加。

## 实现要点/限制

- 统计基于线程调度事件，`time` 为线程在 CPU 上运行的累计时间（纳秒）。
- 使用主备表切换，每个窗口输出并清空对应表。
- 过滤列表通过 BPF map 维护，未设置过滤参数时默认全量采集。
- 用户态会根据配置的窗口大小裁剪过时数据。
