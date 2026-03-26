# System V Message Queue Sniffer

The System V Message Queue sniffer monitors `msgsnd` and `msgrcv` system calls using eBPF tracepoints.

## Overview

- **Type**: eBPF tracepoint-based tracer
- **Target**: `sys_enter_msgsnd`, `sys_exit_msgsnd`, `sys_enter_msgrcv`, `sys_exit_msgrcv`
- **Output Format**: CSV with message queue statistics

## Monitored Data

### Entity Types
- `SysvMsgQueueEntity` - Represents a System V message queue identified by `msqid`

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
| `msqid` | Message queue identifier |
| `msg_type` | Message type (user-defined, positive integer) |

## Usage

### Binary
```bash
./src/witty_profiler/binary/sysv_msg/sysv_msg_sniffer [options]
```

### Options
| Option | Description | Default |
|---------|-------------|----------|
| `-d <dir>` | Direction filter: `send`, `recv`, or `all` | `all` |
| `-i <sec>` | Dump interval in seconds | `2` |
| `-p <pid>` | Target process ID filter | `0` (all processes) |

### Example

```bash
# Monitor all message queue operations
sudo ./src/witty_profiler/binary/sysv_msg/sysv_msg_sniffer -d all -i 2

# Monitor only sends
sudo ./src/witty_profiler/binary/sysv_msg/sysv_msg_sniffer -d send -i 2
```

### Output Format

```csv
timestamp,pid,tid,msqid,direction,bytes,count,msg_type
1709123456789000000,12345,12345,69,send,27,1,1
17091234567891000000,12346,12346,69,recv,27,1,1
```

## Implementation Details

### eBPF Tracepoints
- **sys_enter_msgsnd**: Captures `msgsnd` entry with arguments
- **sys_exit_msgsnd**: Captures `msgsnd` exit with return value
- **sys_enter_msgrcv**: Captures `msgrcv` entry with arguments
- **sys_exit_msgrcv**: Captures `msgrcv` exit with return value

### Data Collection
1. On `msgsnd` entry: Store `msqid`, `msgsz`, and `msg_type` in per-TID map
2. On `msgsnd` exit: If successful, update stats with stored arguments
3. On `msgrcv` entry: Store `msqid`, `msgsz`, and `msgtyp` in per-TID map
4. On `msgrcv` exit: If successful, update stats with actual bytes received

### Message Type
- User-defined positive integer
- Allows selective message receiving (`msgrcv` can filter by type)
- Traced from user-space message buffer

### Double Buffering
- Two BPF maps (`sysv_msg_stats_map_a`, `sysv_msg_stats_map_b`)
- User-space switches between maps for lock-free reading
- Active map controlled by `ipc_config.active_map`

## Testing

See [IPC Test Guide](../../../local/test_ipc_instruction/测试指南.md) for detailed testing instructions.

### Quick Test
```bash
# Terminal 1: Start sniffer
sudo ./src/witty_profiler/binary/sysv_msg/sysv_msg_sniffer -d all -i 2

# Terminal 2: Compile and run test
cd /mnt/d/papers/2026plus/projects/Witty Profiler/local/test_ipc_instruction
gcc -o sysv_msg_test sysv_msg_test.c
./sysv_msg_test
```

## Python Integration

```python
from witty_profiler.tools.ebpftools.sysv_msg_sniffer import SysvMsgSniffer

sniffer = SysvMsgSniffer(
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
- System V IPC is older POSIX standard, still widely used
- Message queues persist after process termination (until explicitly removed)
- Use `ipcs -q` to view existing message queues
- Use `ipcrm -q <msqid>` to remove a message queue

## System V IPC Commands

```bash
# View message queues
ipcs -q

# Create a message queue
ipcmk -Q

# Remove a message queue
ipcrm -q <msqid>

# View all IPC resources
ipcs -a
```

## Comparison with POSIX Message Queues

| Feature | System V MQ | POSIX MQ |
|----------|-------------|-----------|
| Standard | System V IPC | POSIX |
| API | `msgsnd`, `msgrcv` | `mq_send`, `mq_receive` |
| Identifier | Integer `msqid` | String name (in `/dev/mqueue/`) |
| Persistence | Kernel-wide | File system-based |
| Priority | Via message type | Built-in priority |
| Notification | Signal-based | File descriptor-based |
