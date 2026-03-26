"""IPC traffic tests for Anansi sniffer testing.

This module provides test programs for various IPC mechanisms:
- Unix Domain Socket (UDS)
- System V Message Queue
- POSIX Message Queue
- System V Semaphore
- Pipe/FIFO

Usage:
    # Run individual tests
    python3 -m tests.traffic.ipc_traffic.uds_test server
    python3 -m tests.traffic.ipc_traffic.uds_test client
    python3 -m tests.traffic.ipc_traffic.sysv_msg_test
    python3 -m tests.traffic.ipc_traffic.posix_mq_test
    python3 -m tests.traffic.ipc_traffic.sysv_sem_test
    python3 -m tests.traffic.ipc_traffic.pipe_test
"""

__all__ = [
    "uds_test",
    "sysv_msg_test",
    "posix_mq_test",
    "sysv_sem_test",
    "pipe_test",
]
