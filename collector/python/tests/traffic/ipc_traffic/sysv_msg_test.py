"""System V Message Queue test for IPC sniffer testing.

This test creates a System V message queue and sends/receives messages
between parent and child processes.

Requirements:
    pip install sysv_ipc

Usage:
    python3 sysv_msg_test.py
"""

import os
import sys
import time

try:
    import sysv_ipc
except ImportError:
    print("Error: sysv_ipc module not found")
    print("Install with: pip install sysv_ipc")
    sys.exit(1)

MSG_SIZE = 128
KEY_PATH = "/tmp"
KEY_ID = ord('A')


def run_test():
    print("System V Message Queue Test")
    
    key = sysv_ipc.ftok(KEY_PATH, KEY_ID)
    print(f"Key: {key}")
    
    mq = sysv_ipc.MessageQueue(key, flags=sysv_ipc.IPC_CREX, mode=0o666)
    print(f"Message Queue ID: {mq.id}")
    
    pid = os.fork()
    
    if pid == 0:
        time.sleep(1)
        print("[Child] Waiting for message...")
        try:
            message, msg_type = mq.receive(block=True)
            print(f"[Child] Received: {message.decode()} (bytes={len(message)})")
        except Exception as e:
            print(f"[Child] Error: {e}")
        os._exit(0)
    else:
        print("[Parent] Sending message...")
        message = b"Hello from parent process!"
        try:
            mq.send(message, block=True)
            print(f"[Parent] Sent: {message.decode()} (bytes={len(message)})")
        except Exception as e:
            print(f"[Parent] Error: {e}")
        
        os.waitpid(pid, 0)
        print("[Parent] Child process finished")
    
    mq.remove()
    print("Message queue removed")


if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()
    run_test()
