"""POSIX Message Queue test for IPC sniffer testing.

This test creates a POSIX message queue and sends/receives messages
between parent and child processes.

Requirements:
    pip install posix_ipc

Usage:
    python3 posix_mq_test.py
"""

import os
import sys
import time

try:
    import posix_ipc
except ImportError:
    print("Error: posix_ipc module not found")
    print("Install with: pip install posix_ipc")
    sys.exit(1)

QUEUE_NAME = "/test_mq"
MAX_SIZE = 1024
MSG_PRIO = 5


def run_test():
    print("POSIX Message Queue Test")
    print(f"Queue Name: {QUEUE_NAME}")
    
    try:
        posix_ipc.unlink_message_queue(QUEUE_NAME)
    except posix_ipc.ExistentialError:
        pass
    
    mq = posix_ipc.MessageQueue(
        QUEUE_NAME,
        flags=posix_ipc.O_CREX,
        mode=0o644,
        max_messages=10,
        max_message_size=MAX_SIZE
    )
    print(f"Queue opened: {mq.name}")
    
    pid = os.fork()
    
    if pid == 0:
        time.sleep(1)
        print("[Child] Waiting for message...")
        try:
            message, priority = mq.receive()
            print(f"[Child] Received (prio={priority}, bytes={len(message)}): {message.decode()}")
        except Exception as e:
            print(f"[Child] Error: {e}")
        mq.close()
        os._exit(0)
    else:
        print("[Parent] Sending message...")
        message = b"Hello from POSIX MQ!"
        try:
            mq.send(message, priority=MSG_PRIO)
            print(f"[Parent] Sent (prio={MSG_PRIO}, bytes={len(message)}): {message.decode()}")
        except Exception as e:
            print(f"[Parent] Error: {e}")
        
        os.waitpid(pid, 0)
        print("[Parent] Child process finished")
    
    mq.close()
    posix_ipc.unlink_message_queue(QUEUE_NAME)
    print("Message queue removed")


if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()
    run_test()
