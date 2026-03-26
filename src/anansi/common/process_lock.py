"""Provide a process-level file lock for single-instance execution.

Uses a non-blocking exclusive lock so callers can fail fast when another
instance is already running. The lock file also stores minimal metadata
to help users locate the existing instance.

Notes:
    - Unix-only; relies on fcntl.flock.
    - The lock is released on process exit or when release() is called.
"""

from __future__ import annotations

import atexit
import fcntl
import json
import os
import time

from anansi.common.logging import get_logger

LOGGER = get_logger(__name__)


class ProcessFileLock:
    """Acquire an exclusive, non-blocking file lock for process-level exclusion."""

    def __init__(self, lock_path: str, lock_name: str = "process") -> None:
        self._lock_path = lock_path
        self._lock_name = lock_name
        self._fd: int | None = None

    def acquire(self) -> None:
        """Acquire the process lock or raise RuntimeError if already held."""
        if self._fd is not None:
            return
        lock_dir = os.path.dirname(self._lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
        fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            os.close(fd)
            existing_info = self._format_existing_info()
            details = f" {existing_info}" if existing_info else ""
            raise RuntimeError(
                f"Another {self._lock_name} instance is already running "
                f"(online or offline). Stop it before starting a new one."
                f" Lock file: {self._lock_path}.{details}"
            )
        self._fd = fd
        self._write_payload({"pid": os.getpid(), "started_at": time.time()})
        atexit.register(self.release)

    def update_metadata(self, metadata: dict[str, object]) -> None:
        """Update metadata stored in the lock file.

        Args:
            metadata: Additional metadata to persist (merged with existing data).
        """
        if self._fd is None:
            return
        current = self._read_payload_from_fd() or {"pid": os.getpid()}
        current.update(metadata)
        self._write_payload(current)

    def release(self) -> None:
        """Release the lock if held."""
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except (OSError, IOError) as exc:
            LOGGER.debug("Failed to release process lock: %s", exc)
        try:
            os.close(self._fd)
        finally:
            self._fd = None

    def _write_payload(self, payload: dict[str, object]) -> None:
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.ftruncate(self._fd, 0)
            data = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            os.write(self._fd, data.encode("ascii"))
            os.fsync(self._fd)
        except OSError as exc:
            LOGGER.debug("Failed to write pid to lock file: %s", exc)

    def _read_payload_from_fd(self) -> dict[str, object] | None:
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            raw = os.read(self._fd, 4096).decode("ascii", errors="ignore").strip()
            if not raw:
                return None
            return json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.debug("Failed to read lock metadata: %s", exc)
            return None

    def _read_payload_from_path(self) -> dict[str, object] | None:
        try:
            with open(self._lock_path, "r", encoding="ascii", errors="ignore") as f:
                raw = f.read(4096).strip()
            if not raw:
                return None
            return json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.debug("Failed to read lock metadata from file: %s", exc)
            return None

    def _format_existing_info(self) -> str | None:
        payload = self._read_payload_from_path()
        if not payload:
            return None
        pid = payload.get("pid")
        mode = payload.get("mode")
        host = payload.get("host")
        port = payload.get("port")
        duration = payload.get("duration")
        parts = []
        if pid is not None:
            parts.append(f"pid={pid}")
        if mode:
            parts.append(f"mode={mode}")
        if host is not None:
            parts.append(f"host={host}")
        if port is not None:
            parts.append(f"port={port}")
        if duration is not None:
            parts.append(f"duration={duration}")
        if not parts:
            return None
        return "Existing instance: " + ", ".join(parts)
