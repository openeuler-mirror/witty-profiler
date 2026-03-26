# System V Semaphore Sniffer

The System V Semaphore sniffer monitors `semop` and `semtimedop` system calls using eBPF tracepoints.

## Overview

- **Type**: eBPF tracepoint-based tracer
- **Target**: `sys_enter_semop`, `sys_exit_semop`, `sys_enter_semtimedop`, `sys_exit_semtimedop`
- **Output Format**: CSV with semaphore operation statistics

## Monitored Data

### Entity Types
- `SysvSemEntity` - Represents a System V semaphore set identified by `semid`

### Edge Types
- `IPCEdge` - Represents synchronization between processes

### Metrics

| Metric | Description |
|---------|-------------|
| `count` | Number of operations |
| `start_ns` | First operation timestamp (nanoseconds) |
| `end_ns` | Last operation timestamp (nanoseconds) |
| `semid` | Semaphore set identifier |
| `sem_num` | Semaphore number within the set |
| `sem_op_type` | Operation type: `wait` (P), `signal` (V), or `zero` |
| `sem_op_val` | Operation value (positive for V, negative for P) |
| `sem_flg` | Operation flags (IPC_NOWAIT, SEM_UNDO, etc.) |

## Usage

### Binary
```bash
./src/witty_profiler/binary/sysv_sem/sysv_sem_sniffer [options]
```

### Options
| Option | Description | Default |
|---------|-------------|----------|
| `-i <sec>` | Dump interval in seconds | `2` |
| `-p <pid>` | Target process ID filter | `0` (all processes) |

### Example

```bash
# Monitor all semaphore operations
sudo ./src/witty_profiler/binary/sysv_sem/sysv_sem_sniffer -i 2

# Monitor operations from a specific process
sudo ./src/witty_profiler/binary/sysv_sem/sysv_sem_sniffer -p 1234
```

### Output Format

```csv
timestamp,pid,tid,semid,sem_num,sem_op_type,count,sem_op_val,sem_flg
1709123456789000000,8111,8111,0,0,wait,1,-1,0
17091234567891000000,8110,8110,0,0,signal,1,1,0
```

## Implementation Details

### eBPF Tracepoints
- **sys_enter_semop**: Captures `semop` entry with arguments
- **sys_exit_semop**: Captures `semop` exit with return value
- **sys_enter_semtimedop**: Captures `semtimedop` entry with arguments
- **sys_exit_semtimedop**: Captures `semtimedop` exit with return value

### Data Collection
1. On `semop`/`semtimedop` entry: Store `semid`, `sem_num`, `sem_op`, and `sem_flg` in per-TID map
2. On `semop`/`semtimedop` exit: If successful, update stats with stored arguments

### Semaphore Operations

| Operation | sem_op_val | sem_op_type | Description |
|-----------|-------------|--------------|-------------|
| P (wait) | -1 | `wait` | Decrement semaphore, block if zero |
| V (signal) | +1 | `signal` | Increment semaphore, wake waiters |
| Zero | 0 | `zero` | Wait until semaphore is zero |

### Operation Flags
- `IPC_NOWAIT`: Return immediately instead of blocking
- `SEM_UNDO`: Automatically undo on process termination

### Double Buffering
- Two BPF maps (`sysv_sem_stats_map_a`, `sysv_sem_stats_map_b`)
- User-space switches between maps for lock-free reading
- Active map controlled by `ipc_config.active_map`

## Testing

See [IPC Test Guide](../../../local/test_ipc_instruction/测试指南.md) for detailed testing instructions.

### Quick Test
```bash
# Terminal 1: Start sniffer
sudo ./src/witty_profiler/binary/sysv_sem/sysv_sem_sniffer -i 2

# Terminal 2: Compile and run test
cd /mnt/d/papers/2026plus/projects/Witty Profiler/local/test_ipc_instruction
gcc -o sysv_sem_test sysv_sem_test.c
./sysv_sem_test
```

## Python Integration

```python
from witty_profiler.tools.ebpftools.sysv_sem_sniffer import SysvSemSniffer

sniffer = SysvSemSniffer(
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
- System V semaphores are older POSIX standard, still widely used
- Semaphore sets persist after process termination (until explicitly removed)
- Use `ipcs -s` to view existing semaphores
- Use `ipcrm -s <semid>` to remove a semaphore set

## System V IPC Commands

```bash
# View semaphores
ipcs -s

# Create a semaphore set
ipcmk -S <nsems>

# Remove a semaphore set
ipcrm -s <semid>

# View all IPC resources
ipcs -a
```

## Semaphore Patterns

### Binary Semaphore
```c
// Initialize to 1
semid = semget(key, 1, IPC_CREAT | 0666);
semctl(semid, 0, SETVAL, 1);

// P operation (wait)
struct sembuf op = {0, -1, 0};
semop(semid, &op, 1);

// V operation (signal)
struct sembuf op = {0, 1, 0};
semop(semid, &op, 1);
```

### Counting Semaphore
```c
// Initialize to N
semctl(semid, 0, SETVAL, N);

// Wait for N resources
struct sembuf op = {0, -N, 0};
semop(semid, &op, 1);
```

## Comparison with POSIX Semaphores

| Feature | System V Sem | POSIX Sem |
|----------|--------------|------------|
| Standard | System V IPC | POSIX |
| API | `semop`, `semtimedop` | `sem_wait`, `sem_post` |
| Identifier | Integer `semid` | Named semaphore or shared memory |
| Persistence | Kernel-wide | File system-based |
| Operation | Array of semaphores | Single semaphore |
| Timeout | `semtimedop` | `sem_timedwait` |
| Notification | Signal-based | File descriptor-based |

## Troubleshooting

### Common Issues

**Issue**: Semaphore operations not captured
- **Cause**: Process using POSIX semaphores instead of System V
- **Solution**: Verify with `ipcs -s` and use POSIX semaphore sniffer if needed

**Issue**: High contention detected
- **Cause**: Multiple processes waiting on same semaphore
- **Solution**: Analyze `sem_op_type=wait` patterns to identify bottlenecks

**Issue**: Semaphore not cleaned up
- **Cause**: Process crashed without cleanup
- **Solution**: Use `ipcrm -s <semid>` to remove manually
