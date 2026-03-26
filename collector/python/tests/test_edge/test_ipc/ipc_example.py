import time
from multiprocessing import Process, Pipe


def process_a(conn):
    i = 0
    while True:
        msg = f"A -> B : {i}"
        conn.send(msg)
        print(f"[A] 发送: {msg}")

        reply = conn.recv()
        print(f"[A] 接收: {reply}")

        i += 1
        time.sleep(1)


def process_b(conn):
    while True:
        msg = conn.recv()
        print(f"[B] 接收: {msg}")

        reply = "B -> A : ack"
        conn.send(reply)
        print(f"[B] 发送: {reply}")

        time.sleep(1)


if __name__ == "__main__":
    conn1, conn2 = Pipe(duplex=True)

    p1 = Process(target=process_a, args=(conn1,))
    p2 = Process(target=process_b, args=(conn2,))

    p1.start()
    p2.start()

    p1.join()
    p2.join()
