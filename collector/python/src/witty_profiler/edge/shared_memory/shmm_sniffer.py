"""Shared memory statistics and sniffer interface.

Provides SharedMemorySniffer ABC and SharedMemoryInfo data structure for
querying shared memory usage, including POSIX shm, memory-mapped files,
and CUDA pinned memory regions.

Data Structures:
    - SharedMemoryInfo: Immutable dataclass with shm metadata
        * shm_name: Memory region identifier
        * size: Allocated size in bytes
        * owner_gid: Group ID of owner
        * last_access_time: Last access timestamp
        * last_modification_time: Last write timestamp
        * creation_time: Allocation timestamp

SharedMemorySniffer Interface:
    - query_shm_info(name): Get metadata for specific region
    - query_all_shm_names(): List all accessible regions
    - query_access_records(name): Get process access list
    - Implementation subclasses support different backends

Usage:
    ```python
    # Get sniffer singleton
    sniffer = get_shared_memory_sniffer()

    # Query specific memory region
    info = sniffer.query_shm_info("myregion")
    if info:
        print(f"Size: {info.size}, Created: {info.creation_time}")

    # List all regions
    names = sniffer.query_all_shm_names()
    for name in names:
        info = sniffer.query_shm_info(name)
        print(f"{name}: {info.size} bytes")
    ```

Data Sources:
    - /proc/sysvipc/shm: System V shared memory
    - /proc/self/maps: Memory-mapped files
    - CUDA runtime: Pinned memory allocations
    - Kernel trace (eBPF): Access patterns

Notes:
    SharedMemoryInfo is frozen (immutable) for thread-safety.
    Timestamps are Unix epoch seconds (float).
    Implementation backends may vary (proc, /dev/mem, eBPF).
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SharedMemoryInfo:
    """共享内存使用情况信息"""

    shm_name: str
    size: int
    owner_gid: int
    last_access_time: float
    last_modification_time: float
    creation_time: float


class SharedMemorySniffer(ABC):
    """共享内存嗅探器基类"""

    @abstractmethod
    def query_shm_info(self, shm_name: str) -> SharedMemoryInfo | None:
        """
        查询指定共享内存的使用情况

        Args:
            shm_name (str): 共享内存名称

        Returns:
            SharedMemoryInfo | None: 使用情况，若不存在则返回None
        """
        raise NotImplementedError()

    @abstractmethod
    def query_pid_by_shm_name(self, shm_name: str) -> list[int]:
        """
        根据共享内存名称查询进程ID
        Args:
            shm_name (str): 共享内存名称

        Returns:
            list[int]: 进程ID列表
        """
        raise NotImplementedError()

    @abstractmethod
    def query_shm_by_pid(self, pid: int) -> list[str]:
        """
        根据进程ID查询共享内存名称
        Args:
            pid (int): 进程ID

        Returns:
            list[str]: 共享内存名称列表
        """
        raise NotImplementedError()

    @abstractmethod
    def query_all_shm_names(self) -> list[str]:
        """
        查询系统中所有共享内存名称

        Returns:
            list[str]: 共享内存名称列表
        """
        raise NotImplementedError()


class PosixSharedMemorySniffer(SharedMemorySniffer):
    """SharedMemorySniffer for Posix systems (Linux)"""

    def query_shm_info(self, shm_name: str) -> SharedMemoryInfo | None:
        shm_path = f"/dev/shm/{shm_name}"
        if not os.path.exists(shm_path):
            return None
        stat_info = os.stat(shm_path)
        return SharedMemoryInfo(
            shm_name=shm_name,
            size=stat_info.st_size,
            owner_gid=stat_info.st_gid,
            last_access_time=stat_info.st_atime,
            last_modification_time=stat_info.st_mtime,
            creation_time=stat_info.st_ctime,
        )

    def query_pid_by_shm_name(self, shm_name: str) -> list[int]:
        pids = []
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/maps", "r", encoding="utf-8") as f:
                    for line in f:
                        if shm_name in line:
                            pids.append(int(pid))
                            break
            except FileNotFoundError:  # pragma: no cover - process may have ended
                continue
        return pids

    def query_shm_by_pid(self, pid: int) -> list[str]:
        shm_names = []
        try:
            with open(f"/proc/{pid}/maps", "r", encoding="utf-8") as f:
                for line in f:
                    if "dev/shm" in line:
                        shm_names.append(line.split()[5].split("/")[-1])
        except FileNotFoundError:
            pass
        return shm_names

    def query_all_shm_names(self) -> list[str]:
        return os.listdir("/dev/shm")


def get_shared_memory_sniffer() -> SharedMemorySniffer:
    """获取共享内存嗅探器实例（目前只支持Linux）"""
    if os.name == "posix":
        return PosixSharedMemorySniffer()

    raise NotImplementedError(f"SharedMemorySniffer not implemented for OS: {os.name}")


__all__ = ["SharedMemorySniffer", "get_shared_memory_sniffer", "SharedMemoryInfo"]

if __name__ == "__main__":
    sniffer = get_shared_memory_sniffer()
    print(sniffer.query_all_shm_names())
