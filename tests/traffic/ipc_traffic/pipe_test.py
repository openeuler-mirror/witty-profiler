"""Pipe/FIFO test for IPC sniffer testing.

This test creates pipes and sends data between parent and child processes.

Usage:
    python3 pipe_test.py
"""

import os
import sys
import time


def run_simple_pipe():
    """Test simple pipe communication."""
    print("Simple Pipe Test")
    print("=" * 40)
    
    r_fd, w_fd = os.pipe()
    print(f"Created pipe: read_fd={r_fd}, write_fd={w_fd}")
    
    pid = os.fork()
    
    if pid == 0:
        os.close(w_fd)
        print("[Child] Waiting for data...")
        data = os.read(r_fd, 1024)
        print(f"[Child] Received: {data.decode()}")
        os.close(r_fd)
        os._exit(0)
    else:
        os.close(r_fd)
        print("[Parent] Sending data...")
        message = b"Hello from pipe!"
        os.write(w_fd, message)
        print(f"[Parent] Sent: {message.decode()}")
        os.close(w_fd)
        
        os.waitpid(pid, 0)
        print("[Parent] Child process finished")


def run_named_pipe():
    """Test named pipe (FIFO) communication."""
    print("\nNamed Pipe (FIFO) Test")
    print("=" * 40)
    
    fifo_path = "/tmp/test_fifo"
    
    try:
        os.mkfifo(fifo_path)
        print(f"Created FIFO: {fifo_path}")
    except FileExistsError:
        print(f"FIFO already exists: {fifo_path}")
    
    pid = os.fork()
    
    if pid == 0:
        print("[Child] Opening FIFO for reading...")
        with open(fifo_path, 'r') as f:
            data = f.read()
            print(f"[Child] Received: {data}")
        os._exit(0)
    else:
        time.sleep(0.5)
        print("[Parent] Opening FIFO for writing...")
        with open(fifo_path, 'w') as f:
            message = "Hello from named pipe!"
            f.write(message)
            print(f"[Parent] Sent: {message}")
        
        os.waitpid(pid, 0)
        print("[Parent] Child process finished")
        
        os.unlink(fifo_path)
        print(f"Removed FIFO: {fifo_path}")


def run_multi_stage_pipe():
    """Test multi-stage pipe (like shell pipeline)."""
    print("\nMulti-Stage Pipe Test")
    print("=" * 40)
    
    pipe1_r, pipe1_w = os.pipe()
    pipe2_r, pipe2_w = os.pipe()
    
    pid1 = os.fork()
    if pid1 == 0:
        os.close(pipe1_w)
        os.close(pipe2_r)
        os.close(pipe2_w)
        
        data = os.read(pipe1_r, 1024)
        processed = data.upper()
        os.write(pipe1_r + 1, processed)
        os.close(pipe1_r)
        os._exit(0)
    
    pid2 = os.fork()
    if pid2 == 0:
        os.close(pipe1_r)
        os.close(pipe1_w)
        os.close(pipe2_w)
        
        data = os.read(pipe2_r, 1024)
        print(f"[Stage2] Received: {data.decode()}")
        os.close(pipe2_r)
        os._exit(0)
    
    os.close(pipe1_r)
    os.close(pipe2_r)
    
    print("[Parent] Sending data through pipeline...")
    message = b"hello multi-stage pipe"
    os.write(pipe1_w, message)
    print(f"[Parent] Sent: {message.decode()}")
    
    os.close(pipe1_w)
    os.close(pipe2_w)
    
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)
    print("[Parent] All child processes finished")


if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()
    
    run_simple_pipe()
    run_named_pipe()
