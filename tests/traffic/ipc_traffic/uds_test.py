"""Unix Domain Socket test for IPC sniffer testing.

Usage:
    python3 uds_test.py server  # Run server first (will block)
    python3 uds_test.py client  # Run client in another terminal
"""

import os
import socket
import sys
import time

SOCKET_PATH = "/tmp/uds_test.sock"


def server():
    print(f"[Server] Starting...")

    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
        print(f"[Server] Removed existing socket file")

    try:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        server.listen(1)
        print(f"[Server] Listening on {SOCKET_PATH}...")
        print(f"[Server] Waiting for client connection (will block here)...")

        conn, _ = server.accept()
        print("[Server] Client connected!")

        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[Server] Received: {data.decode()}")
            conn.send(b"ACK: " + data)

        conn.close()
        server.close()
        os.remove(SOCKET_PATH)
        print("[Server] Closed")
    except Exception as e:
        print(f"[Server] Error: {e}")
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


def client():
    print(f"[Client] Starting...")

    if not os.path.exists(SOCKET_PATH):
        print(f"[Client] Error: Socket file {SOCKET_PATH} does not exist!")
        print(f"[Client] Please start the server first in another terminal:")
        print(f"[Client]   python3 uds_test.py server")
        return

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        print(f"[Client] Connecting to {SOCKET_PATH}...")
        client.connect(SOCKET_PATH)
        print(f"[Client] Connected!")

        messages = ["Hello UDS", "Test message 1", "Test message 2", "EXIT"]
        for msg in messages:
            client.send(msg.encode())
            print(f"[Client] Sent: {msg}")
            response = client.recv(1024)
            print(f"[Client] Server response: {response.decode()}")
            time.sleep(0.5)

        client.close()
        print("[Client] Closed")
    except Exception as e:
        print(f"[Client] Error: {e}")


if __name__ == "__main__":
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        server()
    elif len(sys.argv) > 1 and sys.argv[1] == "client":
        client()
    else:
        print("Usage:")
        print("  python3 uds_test.py server  # Run server first (will block)")
        print("  python3 uds_test.py client  # Run client in another terminal")
