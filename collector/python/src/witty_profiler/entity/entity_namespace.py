"""Thread-safe context manager for scoping entity namespace prefixes.

Provides EntityNameSpace, a context manager that temporarily overrides
the current entity namespace during entity creation. Used to tag entities
with their discovery source (e.g., "socket_collector", "shm_collector").

Global ID Format with Namespace:
    `[{namespace}]{entity_type}_{unique_id}`
    Example: `[socket_collector]ProcessEntity_1234`

Features:
    - Thread-local namespace stack for multi-threaded safety
    - Nested context manager support (stack-based)
    - Falls back to DEFAULT_NAMESPACE if stack is empty
    - Used by collectors to tag entities by source

Usage:
    ```python
    # Default namespace
    assert DEFAULT_NAMESPACE == EntityNameSpace.get_namespace()

    # Temporarily override for a collector's entity creation
    with EntityNameSpace.set_namespace("socket_collector"):
        assert "socket_collector" == EntityNameSpace.get_namespace()
        # Entities created here use namespace "socket_collector"
        with EntityNameSpace.set_namespace("inner"):
            assert "inner" == EntityNameSpace.get_namespace()
            # Nested context
    # Restores to DEFAULT_NAMESPACE after exit
    ```

Thread Safety:
    Each thread maintains its own namespace stack via threading.local().
    Safe for concurrent collector operations.

Usage in Collectors:
    ```python
    class SocketCollector(RegisteredCollector):
        def get_neighbors_with_edges(self, entity):
            with EntityNameSpace.set_namespace("socket_collector"):
                # Create entities with namespace prefix
                process = ProcessEntity(pid=1234)
    ```

Notes:
    Stack is automatically initialized on first use per thread.
    Popping from empty stack is safe (defensive check in __exit__).
"""

import threading

from witty_profiler.common.constants import DEFAULT_NAMESPACE
from witty_profiler.common.env_manager import EnvInfo
from witty_profiler.common.logging import get_logger

LOGGER = get_logger(__name__)


class EntityNameSpace:
    """用于管理实体命名空间的类。
    用法：
    ```python
    assert DEFAULT_NAMESPACE == EntityNameSpace.get_namespace()
    with EntityNameSpace("new_namespace") as ns:
        assert "new_namespace" == EntityNameSpace.get_namespace()
        # 在此上下文中，实体将使用 "new_namespace"
        with EntityNameSpace("new_namespace 2"):
            assert "new_namespace 2" == EntityNameSpace.get_namespace()
            # 在此上下文中，实体将使用 "new_namespace 2"
    ```
    同时注意，多线程环境下，每个线程有独立的命名空间栈。

    """

    # 使用 thread-local 存储每个线程的命名空间栈
    _thread_local = threading.local()

    def __init__(self, env_info: EnvInfo):
        self._env_info = env_info
        # 初始化线程本地存储中的栈（如果尚不存在）
        if not hasattr(self._thread_local, "stack"):
            self._thread_local.stack = []

    def __enter__(self):
        # 将新的命名空间推入当前线程的栈顶
        self._thread_local.stack.append(self._env_info)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 从当前线程的栈顶弹出命名空间
        # 检查栈是否为空以避免错误，虽然在此设计下通常不应为空
        if self._thread_local.stack:
            self._thread_local.stack.pop()

    @classmethod
    def get_namespace(cls) -> str:
        """
        获取当前线程的活动命名空间。
        如果栈为空，则返回默认的 DEFAULT_NAMESPACE 命名空间。
        """
        stack: list[EnvInfo] = getattr(cls._thread_local, "stack", [])
        if stack:
            last: EnvInfo = stack[-1]
            return last.local_ip
        else:
            return DEFAULT_NAMESPACE


__all__ = ["EntityNameSpace"]
