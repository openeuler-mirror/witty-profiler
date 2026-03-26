"""System V Semaphore test for IPC sniffer testing.

This test creates a System V semaphore set and performs P/V operations
between parent and child processes.

Requirements:
    pip install sysv_ipc

Usage:
    python3 sysv_sem_test.py
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

KEY_PATH = "/tmp"
KEY_ID = ord('S')


def run_test():
    print("System V Semaphore Test")
    
    key = sysv_ipc.ftok(KEY_PATH, KEY_ID)
    print(f"Key: {key}")
    
    sem = sysv_ipc.Semaphore(key, flags=sysv_ipc.IPC_CREX, initial_value=1)
    print(f"Semaphore ID: {sem.id}")
    print("Semaphore initialized to 1")
    
    pid = os.fork()
    
    if pid == 0:
        print("[Child] Waiting for semaphore (P operation)...")
        try:
            sem.P()
            print("[Child] Acquired semaphore")
        except Exception as e:
            print(f"[Child] Error in P: {e}")
        
        time.sleep(1)
        
        print("[Child] Releasing semaphore (V operation)...")
        try:
            sem.V()
            print("[Child] Released semaphore")
        except Exception as e:
            print(f"[Child] Error in V: {e}")
        os._exit(0)
    else:
        print("[Parent] Acquiring semaphore (P operation)...")
        try:
            sem.P()
            print("[Parent] Acquired semaphore")
        except Exception as e:
            print(f"[Parent] Error in P: {e}")
        
        time.sleep(2)
        
        print("[Parent] Releasing semaphore (V operation)...")
        try:
            sem.V()
            print("[Parent] Released semaphore")
        except Exception as e:
            print(f"[Parent] Error in V: {e}")
        
        os.waitpid(pid, 0)
        print("[Parent] Child process finished")
    
    sem.remove()
    print("Semaphore removed")


if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()
    run_test()
