"""Provides thread-safe and non-thread-safe singleton pattern implementations using metaclasses and decorators.

This module implements the singleton pattern through two metaclasses, allowing
    selection of either thread-safe or non-thread-safe versions based on requirements:
    - SingletonMeta + Singleton: Basic singleton implementation without locking,
        suitable for single-threaded environments
    - ThreadSafeSingletonMeta + ThreadSafeSingleton: Thread-safe singleton
         using RLock to protect instance creation and initialization across
         multiple threads
    - Core mechanism: Decorates __new__ and __init__ methods to ensure the
        instance is created on first call to
      get_instance(), with subsequent calls returning the same instance.
      __init__ executes only on first creation (tracked via _sgt_initialized flag)

Usage example:
    class MyController(ThreadSafeSingleton):
        def __init__(self):
            self.data = []

    # Get singleton instance (multiple calls return the same object)
    instance1 = MyController.get_instance()
    instance2 = MyController.get_instance()
    assert instance1 is instance2

Important notes:
    - Always obtain singletons via get_instance() method; direct constructor calls
        are prohibited (creates extra instances)
    - clear_singleton() is intended for test environment cleanup only; do not call
        in production code
    - Prefer ThreadSafeSingleton in multi-threaded environments; use Singleton for
        single-threaded contexts to reduce lock overhead
    - Singleton inheritance is not recommended (subclasses inherit parent's
        _sgt_instance, causing shared state).
      If subclass singletons are needed, have each subclass inherit from the
        appropriate metaclass directly
"""

import threading
from abc import ABC, ABCMeta
from typing import Any

from witty_profiler.common.logging import get_logger

LOGGER = get_logger(__name__)


INSTANCE_ATTR_NAME = "_sgt_instance"
INITIALIZED_ATTR_NAME = "_sgt_initialized"
INSTANCE_LOCK_NAME = "_sgt_lock"


class SingletonMeta(ABCMeta):
    _cls2instances: dict[type, "Singleton"] = {}

    def __call__(cls, *args, **kwargs):

        if cls not in SingletonMeta._cls2instances:
            obj = super().__call__(*args, **kwargs)
            SingletonMeta._cls2instances[cls] = obj
        return SingletonMeta._cls2instances[cls]

    @classmethod
    def get_instance(mcs, cls, *args, **kwargs) -> "Singleton":
        """Return the singleton instance of the class."""
        if cls not in SingletonMeta._cls2instances:
            obj = super().__call__(cls, *args, **kwargs)
            SingletonMeta._cls2instances[cls] = obj
        return SingletonMeta._cls2instances[cls]

    @classmethod
    def clear_singleton(mcs, cls):
        """Clear all singleton instances."""
        LOGGER.warning(
            "NOT EXPECTED: Clear singleton instance (tid: %s) of %s (id: %s)",
            threading.get_native_id(),
            cls.__name__,
            id(cls),
        )
        if cls in SingletonMeta._cls2instances:
            del SingletonMeta._cls2instances[cls]


class ThreadSafeSingletonMeta(ABCMeta):

    _cls2instances: dict[type, "ThreadSafeSingleton"] = {}
    _lock: threading.Lock = threading.RLock()

    def __call__(cls, *args, **kwargs):
        """Create a singleton instance."""
        if cls not in ThreadSafeSingletonMeta._cls2instances:
            with ThreadSafeSingletonMeta._lock:
                if cls not in ThreadSafeSingletonMeta._cls2instances:
                    ThreadSafeSingletonMeta._cls2instances[cls] = super().__call__(
                        *args, **kwargs
                    )
        return ThreadSafeSingletonMeta._cls2instances[cls]

    @classmethod
    def get_instance(mcs, cls, *args, **kwargs) -> "ThreadSafeSingleton":
        """Return the singleton instance of the class."""
        with mcs._lock:
            if cls not in mcs._cls2instances:
                mcs._cls2instances[cls] = super().__call__(cls, *args, **kwargs)
            return mcs._cls2instances[cls]

    @classmethod
    def clear_singleton(mcs, cls):
        """Clear all singleton instances."""
        with mcs._lock:
            if cls in mcs._cls2instances:
                del mcs._cls2instances[cls]


class Singleton(ABC, metaclass=SingletonMeta):

    @classmethod
    def get_instance(cls, *args, **kwargs):
        return SingletonMeta.get_instance(cls, *args, **kwargs)

    @classmethod
    def clear_singleton(cls):
        return SingletonMeta.clear_singleton(cls)


class ThreadSafeSingleton(ABC, metaclass=ThreadSafeSingletonMeta):

    @classmethod
    def get_instance(cls, *args, **kwargs):
        return ThreadSafeSingletonMeta.get_instance(cls, *args, **kwargs)

    @classmethod
    def clear_singleton(cls):
        return ThreadSafeSingletonMeta.clear_singleton(cls)


__all__ = [
    "Singleton",
    "ThreadSafeSingleton",
    "SingletonMeta",
    "ThreadSafeSingletonMeta",
]
