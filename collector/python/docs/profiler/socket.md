# **Socket Sniffer (eBPF) 使用指南（重构版）**

## 功能

- 通过 eBPF kprobe/kretprobe 监控 `tcp_sendmsg` / `udp_sendmsg` / `tcp_recvmsg` / `udp_recvmsg`。
- 按进程与四元组聚合字节数与包数（调用次数）。
- 输出格式支持 CSV 或 msgspec（长度前缀 MessagePack）。
- 支持 fixed LRU / dynamic LRU 两种统计 map 方案。

## 目录结构

- 用户态加载器：`src/witty_profiler/tools/ebpftools/socket_sniffer_c/main.cpp`
- eBPF 源：`src/witty_profiler/tools/ebpftools/socket_sniffer_c/ebpf/*.bpf.c`
- eBPF 公共头：`src/witty_profiler/tools/ebpftools/socket_sniffer_c/ebpf/socket_sniffer_common.h`
- LRU 逻辑：`src/witty_profiler/tools/ebpftools/socket_sniffer_c/lru/`
- 输出逻辑：`src/witty_profiler/tools/ebpftools/socket_sniffer_c/flowdump/`

## 环境要求

- Linux 内核支持 eBPF/BTF（常见 5.x+），需 root 运行；Windows 无法直接使用。
- 依赖：`clang`、`llvm`、`libbpf-dev`、`pkg-config`、`zlib1g-dev`、`libelf-dev`、 `cmake`。

```bash
# debian & ubuntu
apt install -y clang llvm libbpf-dev pkg-config zlib1g-dev libelf-dev cmake  bpftool
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

- **回退方案**：如果架构目录下无 vmlinux.h，CMake 会尝试使用 `src/witty_profiler/tools/ebpftools/vmlinux/vmlinux.h` 作为回退

## 编译

### 选择编译通路

- **LRU 类型**：
  - `SOCKET_LRU_DYNAMIC=ON`（默认）→ array-of-maps 动态调整
  - `SOCKET_LRU_DYNAMIC=OFF` → fixed 双 LRU map
- **输出类型**：
  - `SOCKET_OUTPUT_MSGSPEC=ON` → msgspec
  - `SOCKET_OUTPUT_MSGSPEC=OFF`（默认）→ CSV

### 构建命令

```bash
# 推荐：使用构建脚本
witty-profiler-build
# 或
python -m witty_profiler.tools.build

# 手动构建（socket_sniffer）
cmake -B src/witty_profiler/binary/socket -S src/witty_profiler/tools/ebpftools/socket_sniffer_c -DSOCKET_LRU_DYNAMIC=OFF -DSOCKET_OUTPUT_MSGSPEC=OFF
cmake --build src/witty_profiler/binary/socket
```

产物：

- `src/witty_profiler/binary/socket/socket_sniffer_bpf.o`（eBPF 对象）
- `src/witty_profiler/binary/socket/socket_sniffer`（用户态加载器）

## 运行

```bash
sudo src/witty_profiler/binary/socket/socket_sniffer -p <PID> -d send|recv|all -m <entries> -i <sec> -o src/witty_profiler/binary/socket/socket_sniffer_bpf.o
```

### 参数说明

- `-v`：打印当前二进制的 LRU 与输出类型（MSGSPEC 或 CSV）后退出。
- `-p <pid>`：仅统计该进程（0 或缺省表示全部进程）。
- `-o <path>`：BPF 对象文件路径，默认 `socket_sniffer_bpf.o`（当前工作目录）。
- `-d send|recv|all`：挂钩方向，默认 `all`。
- `-m <entries>`：
  - dynamic：动态伸缩 LRU entries
  - fixed：固定 LRU entries
- `-i <seconds>`：输出打印间隔（秒），默认 1。

### 版本一致性校验

- 加载 eBPF 后会读取其只读版本信息，校验 LRU 类型是否与用户态一致。
- 不一致时会直接退出并提示 mismatch。

## 输出格式

### CSV

字段顺序：

```text
function, local_pid, local_tid, local_addr, local_port, remote_addr, remote_port, start_time, end_time, data_size_total, packet_cnt
```

示例：

```csv
tcp_sendmsg,12345,12345,10.0.0.1,52512,10.0.0.2,443,1700000000000000000,1700000000001000000,2048,3
```

### msgspec

- 输出为 **长度前缀（4 字节大端）+ MessagePack 数组**。
- 数组字段顺序与 CSV 相同，共 11 个元素。
- 适合二进制管道或后续解析，不建议直接在终端查看。

## 实现要点/限制

- 覆盖发送与接收路径，方向可通过 `-d` 过滤。
- 仅 IPv4；IPv6 未实现。
- CMake 会自动识别 `CMAKE_SYSTEM_PROCESSOR`，为 eBPF 编译传入正确的 `__TARGET_ARCH_*` 宏，并优先从 `src/witty_profiler/tools/ebpftools/vmlinux/<arch>/vmlinux.h` 包含（无则回退到 `src/witty_profiler/tools/ebpftools/vmlinux/vmlinux.h`）。
