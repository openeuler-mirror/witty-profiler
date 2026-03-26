# Pipe/FIFO Sniffer

The Pipe/FIFO sniffer monitors anonymous pipes and named pipes (FIFOs) on the system using eBPF.

## Overview

- **Type**: eBPF-based kernel tracer
- **Target**: `pipe_write`, `pipe_read` kernel functions
- **Output Format**: CSV with pipe statistics

## Monitored Data

### Entity Types
- `PipeInodeEntity` - Represents a pipe identified by its inode number

### Edge Types
- `IPCEdge` - Represents data flow between processes through pipes

### Metrics

| Metric | Description |
|---------|-------------|
| `bytes` | Number of bytes transferred |
| `count` | Number of read/write operations |
| `start_ns` | First operation timestamp (nanoseconds) |
| `end_ns` | Last operation timestamp (nanoseconds) |
| `direction` | `read` or `write` |

## Usage

### Binary
```bash
./src/anansi/binary/pipe/pipe_sniffer [options]
```

### Options
| Option | Description | Default |
|---------|-------------|----------|
| `-d <dir>` | Direction filter: `read`, `write`, or `all` | `all` |
| `-i <sec>` | Dump interval in seconds | `2` |
| `-p <pid>` | Target process ID filter | `0` (all processes) |

### Example

```bash
# Monitor all pipe operations
sudo ./src/anansi/binary/pipe/pipe_sniffer -d all -i 2

# Monitor only writes from a specific process
sudo ./src/anansi/binary/pipe/pipe_sniffer -d write -p 1234
```

### Output Format

```csv
timestamp,pid,tid,inode,direction,bytes,count
1709123456789000000,12345,12345,12345,write,1024,1
17091234567891000000,12346,12346,12345,read,1024,1
```

## Implementation Details

### eBPF Programs
- **kprobe/pipe_write**: Captures write operations
- **kretprobe/pipe_write**: Captures write completion and byte count
- **kprobe/pipe_read**: Captures read operations
- **kretprobe/pipe_read**: Captures read completion and byte count

### Data Collection
1. On `pipe_write` entry: Record timestamp and process info
2. On `pipe_write` exit: Get byte count from return value, update stats
3. On `pipe_read` entry: Record timestamp and process info
4. On `pipe_read` exit: Get byte count from return value, update stats

### Double Buffering
- Two BPF maps (`pipe_stats_map_a`, `pipe_stats_map_b`)
- User-space switches between maps for lock-free reading
- Active map controlled by `ipc_config.active_map`

## Testing

See [IPC Test Guide](../../../local/test_ipc_instruction/测试指南.md) for detailed testing instructions.

### Quick Test
```bash
# Terminal 1: Start sniffer
sudo ./src/anansi/binary/pipe/pipe_sniffer -d all -i 2

# Terminal 2: Create pipe traffic
ls -la | grep "test"
```

## Python Integration

```python
from anansi.tools.ebpftools.pipe_sniffer import PipeSniffer

sniffer = PipeSniffer(
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
- Anonymous pipes and FIFOs are both monitored
- Pipe inode is used as the unique identifier
