# **Cache Miss Monitor (eBPF) 使用指南**

## 功能

- 通过 perf_event 采样 `PERF_COUNT_HW_CACHE_MISSES`。
- 可按 `(pid, tid, cpu)` 过滤 cache miss 次数，不传参数时默认全采集。
- 统计结果按 `(cpu, tgid, pid)` 分组输出。
- 以固定时间窗口输出，并在窗口结束时主备表切换。

## 目录结构

- 用户态加载器：`src/anansi/tools/ebpftools/cache_monitor_c/main.cpp`
- eBPF 源：`src/anansi/tools/ebpftools/cache_monitor_c/ebpf/cache_miss_monitor.bpf.c`
- 构建脚本：`src/anansi/tools/ebpftools/cache_monitor_c/CMakeLists.txt`

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
  - **自动生成**：若 `src/anansi/tools/ebpftools/vmlinux/<arch>/vmlinux.h` 不存在，CMake 会在配置阶段自动调用 `bpftool btf dump` 生成
  - **手动生成**（如自动生成失败）：

```bash
# x86_64
bpftool btf dump file /sys/kernel/btf/vmlinux format c > src/anansi/tools/ebpftools/vmlinux/x86_64/vmlinux.h

# aarch64
bpftool btf dump file /sys/kernel/btf/vmlinux format c > src/anansi/tools/ebpftools/vmlinux/aarch64/vmlinux.h
```

- **回退方案**：如果架构目录下无 vmlinux.h，CMake 会尝试使用 `src/anansi/tools/ebpftools/vmlinux/vmlinux.h` 作为回退

## 编译

```bash
# 推荐：使用构建脚本
anansi-build
# 或
python -m anansi.tools.build

# 手动构建（cache_miss_monitor）
cmake -B src/anansi/binary/cache_miss -S src/anansi/tools/ebpftools/cache_monitor_c -DCACHE_OUTPUT_MSGSPEC=OFF
cmake --build src/anansi/binary/cache_miss
```

### 输出格式选择

- `-DCACHE_OUTPUT_MSGSPEC=OFF`（默认）：CSV
- `-DCACHE_OUTPUT_MSGSPEC=ON`：msgspec（长度前缀 MessagePack）

产物：

- `src/anansi/binary/cache_miss/cache_miss_monitor_bpf.o`（eBPF 对象）
- `src/anansi/binary/cache_miss/cache_miss_monitor`（用户态加载器）

## 运行

```bash
sudo src/anansi/binary/cache_miss/cache_miss_monitor [-v] [-p <PID>] [-t <TID>] [-c <CPU_ID>] [-i <SECONDS>] [-d <SECONDS>] [-s <PERIOD>] [-o src/anansi/binary/cache_miss/cache_miss_monitor_bpf.o]
```

### 参数说明

- `-p <pid>`：目标进程 TGID（进程号）；缺省表示全部进程。
- `-t <tid>`：目标线程 PID（TID）；缺省表示全部线程。
- `-c <cpu>`：目标 CPU 核心 ID；缺省表示对所有 CPU 附着 perf_event。
- `-i <seconds>`：统计窗口切换间隔，默认 1 秒。
- `-d <seconds>`：总采样时长，默认 0 表示持续运行直到退出。
- `-s <period>`：perf 采样周期（cache miss 事件溢出周期），默认 1000，用于降低节流导致的停滞。
- `-o <path>`：BPF 对象文件路径，默认 `cache_miss_monitor_bpf.o`（当前工作目录）。
- `-v`：输出当前二进制的输出格式并退出。

## 输出格式

### CSV

```text
cpu,tgid,pid,total,l1i,llc
```

### msgspec

- 输出为 **长度前缀（4 字节大端）+ MessagePack 数组**。
- 数组字段顺序：`[cpu, tgid, pid, total, l1i, llc]`。

示例：

```text
cpu,tgid,pid,total,l1i,llc
0,12345,12345,5120,1200,3920
1,12345,12345,4870,1100,3770
```

## 实现要点/限制

- 未指定 CPU 时会对所有 CPU 附着 perf_event；指定 CPU 时若线程迁移到其他 CPU，计数会被过滤，建议将目标线程绑核以获得稳定结果。
- 可按 `(pid, tid, cpu)` 过滤，不传参数则统计全系统范围内的 cache miss，输出按 `(cpu, tgid, pid)` 分组。
- 统计指标为 L1I miss 与 LLC miss，`total` 为二者之和。
- 主备表切换以固定间隔进行，单窗口内的统计会被输出并清空对应表。
- 若计数表达到容量上限，新增键会被丢弃；程序会在 stderr 输出每个窗口的 `entries` 与 `drops` 统计。
- 若某窗口 `entries=0` 且 `drops=0`，程序会重新启用 perf 事件以缓解节流导致的停滞。
- 若 `sample_period` 过小（如 1），硬件事件可能被内核节流导致长期无输出，建议提高 `-s`。
- 需要内核支持硬件 perf event；虚拟化环境下可能不可用或计数不稳定。
