# POSIX Message Queue Sniffer

The POSIX Message Queue sniffer monitors `mq_timedsend` and `mq_timedreceive` system calls using eBPF tracepoints.

## Overview

- **Type**: eBPF tracepoint-based tracer
- **Target**: `sys_enter_mq_timedsend`, `sys_exit_mq_timedsend`, `sys_enter_mq_timedreceive`, `sys_exit_mq_timedreceive`
- **Output Format**: CSV with message queue statistics

## Monitored Data

### Entity Types
- `PosixMqEntity` - Represents a POSIX message queue identified by its name

### Edge Types
- `IPCEdge` - Represents message passing between processes

### Metrics

| Metric | Description |
|---------|-------------|
| `bytes` | Number of bytes in the message |
| `count` | Number of send/recv operations |
| `start_ns` | First operation timestamp (nanoseconds) |
| `end_ns` | Last operation timestamp (nanoseconds) |
| `direction` | `send` or `recv` |
| `mqd` | Message queue descriptor |
| `msg_prio` | Message priority (0-255) |

## Usage

### Binary
```bash
./src/anansi/binary/posix_mq/posix_mq_sniffer [options]
```

### Options
| Option | Description | Default |
|---------|-------------|----------|
| `-d <dir>` | Direction filter: `send`, `recv`, or `all` | `all` |
| `-i <sec>` | Dump interval in seconds | `2` |
|`-p <pid>` | Target process ID filter | `0` (all processes) |

### Example

```bash
# Monitor all message queue operations
sudo ./src/anansi/binary/posix_mq/posix_mq_sniffer -d all -i 2

# Monitor only receives
sudo ./src/anansi/binary/posix_mq/posix_mq_sniffer -d recv -i 2
```

### Output Format

```csv
timestamp,pid,tid,mqd,direction,bytes,count,msg_prio
1709123456789000000,12345,12345,3,send,16,1,5
17091234567891000000,12346,12346,3,recv,16,1,5
```

## Implementation Details

### eBPF Tracepoints
- **sys_enter_mq_timedsend**: Captures `mq_timedsend` entry with arguments
- **sys_exit_mq_timedsend**: Captures `mq_timedsend` exit with return value
- **sys_enter_mq_timedreceive**: Captures `mq_timedreceive` entry with arguments
- **sys_exit_mq_timedreceive**: Captures `mq_timedreceive` exit with return value

### Data Collection
1. On `mq_timedsend` entry: Store `mqdes`, `msg_len`, and `msg_prio` in per-TID map
2. On `mq_timedsend` exit: If successful, update stats with stored arguments
3. On `mq_timedreceive` entry: Store `mqdes` and `msg_len` in per-TID map
4. On `mq_timedreceive` exit: If successful, update stats with actual bytes received

### Message Priority
- Integer value 0-255
- Higher priority messages are received first
- Built-in feature of POSIX message queues

### Double Buffering
- Two BPF maps (`posix_mq_stats_map_a`, `posix_mq_stats_map_b`)
- User-space switches between maps for lock-free reading
- Active map controlled by `ipc_config.active_map`

## Testing

See [IPC Test Guide](../../../local/test_ipc_instruction/测试指南.md) for detailed testing instructions.

### Quick Test
```bash
# Terminal 1: Start sniffer
sudo ./src/anansi/binary/posix_mq/posix_mq_sniffer -d all -i 2

# Terminal 2: Compile and run test
cd /mnt/d/papers/2026plus/projects/Anansi/local/test_ipc_instruction
gcc -o posix_mq_test posix_mq_test.c -lrt
./posix_mq_test
```

## Python Integration

```python
from anansi.tools.ebpftools.posix_mq_sniffer import PosixMqSniffer

sniffer = PosixMqSniffer(
    direction="all",  # "send", "recv", or "all"
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
- POSIX message queues are part of the POSIX real-time extensions
- Queues are represented as files in `/dev/mqueue/`
- Requires `librt` (real-time library)
- Use `ls /dev/mqueue/` to view existing queues

## POSIX MQ File System

```bash
# Mount mqueue filesystem (if not already mounted)
sudo mount -t mqueue none /dev/mqueue

# View existing queues
ls -l /dev/mqueue/

# View queue properties (size, messages, etc.)
cat /dev/mqueue/<queue_name>
```

## Comparison with System V Message Queues

| Feature | POSIX MQ | System V MQ |
|----------|-----------|-------------|
| Standard | POSIX | System V IPC |
| API | `mq_send`, `mq_receive` | `msgsnd`, `msgrcv` |
| Identifier | String name | Integer `msqid` |
| Persistence | File system-based | Kernel-wide |
| Priority | Built-in (0-255) | Via message type |
| Notification | File descriptor-based | Signal-based |
| Monitoring | File system tools | `ipcs` command |

## Configuration

### System Limits
```bash
# View current limits
ulimit -a | grep queue

# Increase message queue size limit
ulimit -q 819200
```

### Kernel Parameters
```bash
# View mqueue parameters
cat /proc/sys/fs/mqueue/*

# Adjust maximum queue size
echo 819200 | sudo tee /proc/sys/fs/mqueue/msg_max
```
