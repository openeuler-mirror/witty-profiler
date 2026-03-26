# Unix Domain Socket Sniffer

The Unix Domain Socket (UDS) sniffer monitors local socket communication using eBPF.

## Overview

- **Type**: eBPF-based kernel tracer
- **Target**: `unix_stream_sendmsg`, `unix_stream_recvmsg`, `unix_dgram_sendmsg`, `unix_dgram_recvmsg` kernel functions
- **Output Format**: CSV with socket statistics

## Monitored Data

### Entity Types
- `SocketEntity` - Represents a Unix Domain Socket endpoint

### Edge Types
- `IPCEdge` - Represents data flow between processes through UDS

### Metrics

| Metric | Description |
|---------|-------------|
| `bytes` | Number of bytes transferred |
| `count` | Number of send/recv operations |
| `start_ns` | First operation timestamp (nanoseconds) |
| `end_ns` | Last operation timestamp (nanoseconds) |
| `direction` | `read` or `write` |
| `socket_type` | `1` (SOCK_STREAM) or `2` (SOCK_DGRAM) |
| `peer_inode` | Inode of the peer socket endpoint |

## Usage

### Binary
```bash
./src/witty_profiler/binary/uds/unix_socket_sniffer [options]
```

### Options
| Option | Description | Default |
|---------|-------------|----------|
| `-d <dir>` | Direction filter: `read`, `write`, or `all` | `all` |
| `-i` | Dump interval in seconds | `2` |
| `-p` | Target process ID filter | `0` (all processes) |

### Example

```bash
# Monitor all UDS operations
sudo ./src/witty_profiler/binary/uds/unix_socket_sniffer -d all -i 2

# Monitor only stream sockets
sudo ./src/witty_profiler/binary/uds/unix_socket_sniffer -d all -i 2
```

### Output Format

```csv
timestamp,pid,tid,inode,socket_type,direction,bytes,count,peer_inode
1709123456789000000,12345,12345,12345,1,write,11,1,12346
17091234567891000000,12346,12346,12346,1,read,11,1,12345
```

## Implementation Details

### eBPF Programs
- **kprobe/unix_stream_sendmsg**: Captures stream socket sends
- **kretprobe/unix_stream_sendmsg**: Captures send completion
- **kprobe/unix_stream_recvmsg**: Captures stream socket receives
- **kretprobe/unix_stream_recvmsg**: Captures receive completion
- **kprobe/unix_dgram_sendmsg**: Captures datagram socket sends
- **kretprobe/unix_dgram_sendmsg**: Captures send completion
- **kprobe/unix_dgram_recvmsg**: Captures datagram socket receives
- **kretprobe/unix_dgram_recvmsg**: Captures receive completion

### Data Collection
1. On send/recv entry: Record timestamp, process info, and socket inode
2. On send/recv exit: Get byte count from return value, update stats
3. Extract peer inode from `struct unix_sock`

### Socket Type Detection
- SOCK_STREAM (1): Connection-oriented, reliable (like TCP)
- SOCK_DGRAM (2): Connectionless, unreliable (like UDP)

### Double Buffering
- Two BPF maps (`uds_stats_map_a`, `uds_stats_map_b`)
- User-space switches between maps for lock-free reading
- Active map controlled by `ipc_config.active_map`

## Testing

See [IPC Test Guide](../../../local/test_ipc_instruction/测试指南.md) for detailed testing instructions.

### Quick Test
```bash
# Terminal 1: Start sniffer
sudo ./src/witty_profiler/binary/uds/unix_socket_sniffer -d all -i 2

# Terminal 2: Start UDS server
cd /mnt/d/papers/2026plus/projects/Witty Profiler/local/test_ipc_instruction
python3 uds_test.py server

# Terminal 3: Start UDS client
python3 uds_test.py client
```

## Python Integration

```python
from witty_profiler.tools.ebpftools.uds_sniffer import UdsSniffer

sniffer = UdsSniffer(
    direction="all",  # "read", "write", or "all"
    interval=2,       # dump interval in seconds
    target_pid=None   # None for all processes
)

# Start sniffer
sniffer.start()

# Get collected events
events = sniffer.get_events()

# Stop sniffer
sniffer.stop()
```

## Notes

- Requires root privileges (eBPF)
- Works on Linux 5.8+ with BTF support
- Monitors both SOCK_STREAM and SOCK_DGRAM sockets
- UDS is not visible at TCP/UDP level, making eBPF essential
- Peer inode tracking allows building bidirectional communication graphs

## Comparison with TCP/UDP

| Feature | Unix Domain Socket | TCP/UDP |
|----------|-------------------|-----------|
| Scope | Local only | Network-wide |
| Visibility | Not at TCP/UDP level | Visible at network layer |
| Performance | Higher (no network stack) | Lower (network overhead) |
| Security | File system permissions | Network policies |
| Monitoring | Requires eBPF | Can use netfilter/tcpdump |
