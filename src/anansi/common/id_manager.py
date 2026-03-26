"""Utilities for managing globally unique identifiers for entities and edges.

Provides GlobalIDManager singleton and IdObject mixin for deduplicating
entities and edges across collectors. The manager maintains a registry of
all objects keyed by their global_id to prevent duplicate nodes/edges
during graph construction.

Key Components:
    - IdObject: Mixin base class requiring subclasses to define global_id property
    - GlobalIDManager: Singleton registry mapping global_id strings to objects

Features:
    - Global ID deduplication via singleton registry
    - Lookup by global_id with default fallback
    - Runtime conflict detection (duplicate ID prevention)
    - ID release and update operations for cleanup
    - create_ensure_unique_id() class method for auto-registration
    - Thread-safe with optimistic read locking pattern

Thread Safety:
    - Read operations (exists, lookup) are lock-free using Python GIL atomicity
    - Write operations (record, release, update) are protected by RLock
    - record_or_get() provides atomic get-or-create semantics
    - Suitable for read-heavy workloads in multi-threaded collectors

Usage:
    ```python
    class MyEntity(IdObject):
        @property
        def global_id(self):
            return f"[namespace]{self.entity_type}_{self.unique_id}"

    # Auto-register with deduplication
    entity = MyEntity.create_ensure_unique_id(...)
    # or manually
    manager = GlobalIDManager.get_instance()
    manager.record(entity.global_id, entity)
    existing = manager.lookup_by_global_id(entity.global_id)
    ```
"""

import threading
from abc import ABC
from typing import Any, Tuple

from anansi.common.logging import get_logger
from anansi.common.singleton import Singleton

LOGGER = get_logger(__name__)


class IdObject(ABC):
    """Mixin that requires subclasses to expose a stable ``global_id``."""

    def __lt__(self, other: "IdObject") -> bool:
        return self.global_id < other.global_id

    @property
    def global_id(self) -> str:
        """To be implemented by subclasses, return a unique global identifier."""
        raise NotImplementedError

    def __str__(self) -> str:
        return self.global_id

    @classmethod
    def create_ensure_unique_id(cls, *args, **kwargs) -> "IdObject":
        """Create or retrieve a unique instance with thread-safe deduplication."""
        obj: IdObject = cls(*args, **kwargs)
        if obj.global_id is None:
            raise RuntimeError("Global ID cannot be None")
        manager: GlobalIDManager = GlobalIDManager.get_instance()
        result, _ = manager.record_or_get(obj.global_id, obj)
        return result

    def match_recorded_global_id(self) -> bool:
        """Check if the given global_id matches the pattern of this class."""
        manager: GlobalIDManager = GlobalIDManager.get_instance()
        existing_obj = manager.lookup_by_global_id(self.global_id)
        return existing_obj is self


class GlobalIDManager(Singleton):
    """Thread-safe singleton registry for objects keyed by global identifier.

    Thread Safety Design:
        - Read operations (exists, lookup) are lock-free using Python GIL atomicity
        - Write operations (record, release, update) are protected by RLock
        - record_or_get() provides atomic get-or-create semantics

    This design is optimized for read-heavy workloads where entity/edge
    lookups are far more frequent than insertions.
    """

    _global_id_map: dict[str, Any] = {}
    _global_obj_2_id_map: dict[int, str] = {}

    def __init__(self):
        self._write_lock = threading.RLock()
        GlobalIDManager._global_id_map: dict[str, Any] = {}
        GlobalIDManager._global_obj_2_id_map: dict[int, str] = {}

    def exists(self, global_id: str) -> bool:
        """Check if global_id exists in registry (lock-free read)."""
        return global_id in self._global_id_map

    def lookup_by_global_id(self, gid: str, default=None) -> Any:
        """Lookup object by global_id (lock-free read)."""
        return self._global_id_map.get(gid, default)

    def record(self, global_id: str, obj: IdObject):
        """Record a new global_id -> object mapping.

        Raises:
            RuntimeError: If global_id already exists
        """
        with self._write_lock:
            if global_id in self._global_id_map:
                raise RuntimeError(f"Global ID {global_id} already exists")
            self._global_id_map[global_id] = obj
            self._global_obj_2_id_map[id(obj)] = global_id

    def record_or_get(self, global_id: str, obj: IdObject) -> Tuple[Any, bool]:
        """Atomically record or retrieve an existing object.

        Args:
            global_id: The global identifier to register
            obj: The object to register if global_id doesn't exist

        Returns:
            Tuple of (object, is_new) where:
            - object: The registered object (either existing or newly added)
            - is_new: True if object was newly registered, False if already existed
        """
        with self._write_lock:
            if global_id in self._global_id_map:
                return self._global_id_map[global_id], False
            self._global_id_map[global_id] = obj
            self._global_obj_2_id_map[id(obj)] = global_id
            return obj, True

    def try_release_global_id(self, gid: str):
        """Release a global_id from the registry."""
        with self._write_lock:
            if gid in self._global_id_map:
                obj = self._global_id_map[gid]
                del self._global_id_map[gid]
                del self._global_obj_2_id_map[id(obj)]

    def update_id(self, obj, new_id_str: str):
        """Update the global_id for an existing object."""
        with self._write_lock:
            obj_id: int = id(obj)
            if obj_id in self._global_obj_2_id_map:
                old_gid_str: str = self._global_obj_2_id_map[obj_id]
                old_obj = self._global_id_map[old_gid_str]
                if old_obj is obj:
                    if new_id_str in self._global_id_map:
                        raise RuntimeError(f"Global ID {new_id_str} already exists")
                    del self._global_id_map[old_gid_str]
                    self._global_id_map[new_id_str] = obj
                    self._global_obj_2_id_map[obj_id] = new_id_str
                    return
            raise RuntimeError("Object not found in GlobalIDManager")


__all__ = ["GlobalIDManager", "IdObject"]
