import os
import threading
import time

import psutil


def worker():
    pid = os.getpid()
    # 获取当前线程的系统级线程 ID（TID）
    tid = threading.get_native_id()  # Python 3.8+
    # 或者用：tid = psutil.Process().pid （但这是进程 PID，不是线程 TID）

    print(f"Worker thread started with TID: {tid}")
    print(f"Current Affinity: {psutil.Process().cpu_affinity()}")

    # 可用的 CPU 列表
    cpus = psutil.Process().cpu_affinity()
    i = 0
    while True:
        i += 1
        cpu = cpus[i % len(cpus)]
        try:
            # 创建线程对应的 psutil.Process 对象（注意：在 Linux 上可用 TID）
            thread_proc = psutil.Process(tid)
            thread_proc.cpu_affinity([cpu])  # 绑定到指定 CPU
            print(f"[{time.time():.2f}] Process {pid} Thread {tid} bound to CPU {cpu}")
        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError) as e:
            print(f"Failed to set affinity: {e}")
            break

        # 执行一些计算任务（可选）
        total = sum(j * j for j in range(100000))
        time.sleep(1)  # 每秒切换一次 CPU
        print(f"[{time.time():.2f}] Thread {tid} total: {total}")


if __name__ == "__main__":
    t = threading.Thread(target=worker)
    t.start()
    t.join()
