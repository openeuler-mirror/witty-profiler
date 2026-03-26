"""Context manager for subprocess lifecycle management.

Provides ProcessContextManager, a context manager that starts a subprocess
and ensures clean shutdown with graceful termination followed by force kill
if necessary.

Usage:
    ```python
    def worker_fn(name, count):
        for i in range(count):
            print(f"{name}: {i}")

    with ProcessContextManager(worker_fn, "worker", 5) as process:
        # Code here runs while subprocess is active
        print(f"Subprocess PID: {process.pid}")
    # Subprocess is gracefully shut down after exiting the context
    ```

Shutdown Sequence:
    1. Send SIGTERM to subprocess (graceful termination)
    2. Wait up to 3 seconds for graceful exit
    3. If still alive, call terminate() (immediate shutdown)
    4. Wait up to 2 seconds for termination
    5. Context exits (exception not suppressed)

Parameters:
    target_func: Callable to run in subprocess
    *args: Positional arguments for target_func
    **kwargs: Keyword arguments for target_func

Attributes:
    timeout: Grace period for SIGTERM (default: 3 seconds)
    process: Multiprocessing.Process object (accessible in context)

Notes:
    Used by test fixtures to safely spawn collector processes.
    Platform-dependent: SIGTERM may not work on Windows (OSError caught).
    Always ensures process cleanup; exceptions not suppressed.
"""

import multiprocessing
import os
import signal

from witty_profiler.common.logging import get_logger

LOGGER = get_logger(__name__)


class ProcessContextManager:
    """
    **用于启动进程并管理生命周期**
    示例：
    ```python
    with ProcessContextManager(target_func, *args, **kwargs) as process:
        # 运行代码
        # ...
        # 运行结束
    ```
    进程结束后，会自动调用__exit__方法，并返回False，表示不处理异常
    """

    def __init__(self, target_func, *args, **kwargs):
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs
        self.process = None
        self.timeout = 3  # 优雅退出等待时间，单位秒

    def __enter__(self):
        self.process = multiprocessing.Process(
            target=self.target_func, args=self.args, kwargs=self.kwargs
        )
        LOGGER.info("start process with %s", multiprocessing.get_start_method())
        self.process.start()
        return self.process  # 可选：返回进程对象供外部使用

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.process or not self.process.is_alive():
            return False
        pid = self.process.pid
        try:
            # === 第一步：尝试发送 SIGTERM（模拟终止信号）===
            LOGGER.info("Sending SIGTERM to process PID %d", pid)
            os.kill(pid, signal.SIGTERM)
        except (OSError, AttributeError, ValueError):  # pragma: no cover
            # 如果失败（如进程已退出、Windows 不支持等），跳过
            LOGGER.warning("Failed to send SIGTERM to process PID %d", pid)
        # 等待优雅退出
        self.process.join(timeout=self.timeout)
        if self.process.is_alive():
            LOGGER.warning("Process PID %d did not exit gracefully", pid)

        # === 第二步：若仍存活，强杀 ===
        if self.process.is_alive():  # pragma: no cover : exceptions
            self.process.terminate()
            self.process.join(timeout=2)

        return False  # 不抑制异常
