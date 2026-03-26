import os
import traceback
from typing import Dict, List, Optional

from anansi.common.constants import CONNECTION_TYPE_TCP, CONNECTION_TYPE_UDP
from anansi.common.logging import get_logger
from anansi.common.str_converter import list_to_range_str, range_str_to_list
from anansi.entity.deployment.gpu_deployment import GPUDeploymentManager
from anansi.entity.deployment.npu_deployment import NPUDeploymentManager
from anansi.entity.entity_base import Entity, field

LOGGER = get_logger(__name__)


class ProcessEntity(Entity):
    """
    Entity representing a process node
    """

    pid: int = field(default=-1)
    ppid: int = field(default=-1)
    name: Optional[str] = field(default_factory=lambda: None)
    cmdline: Optional[str] = field(default_factory=lambda: None)

    @property
    def unique_id(self) -> str:
        return f"pid={self.pid},ppid={self.ppid}"

    def _cachable_str(self) -> str:
        return f"ProcessEntity(pid={self.pid},ppid={self.ppid},name={self.name},cmdline={self.cmd_line_abbr})"

    def __post_init__(self):
        if self.pid == -1:
            self.pid = self._get_pid_place_holder()
            LOGGER.warning(
                f"ProcessEntity created without PID, assigned placeholder PID {self.pid}"
            )

        if self.ppid < 0 and self.pid > 0:
            self.ppid = self._get_ppid(self.pid)
        if self.name is None and self.pid > 0:
            self.name = self._parse_name(self.pid)
        if self.cmdline is None and self.pid > 0:
            self.cmdline = self._parse_cmd_line(self.pid)

        super().__post_init__()

    @classmethod
    def _get_pid_place_holder(cls):
        """
        Get a placeholder for process ID
        """

        if not hasattr(cls, "_placeholder"):
            cls._placeholder = -1000

        cls._placeholder -= 1
        return cls._placeholder

    def _get_ppid(self, pid):
        """Try to parse parent process ID from /proc/[pid]/stat"""
        import os

        try:
            with open(f"/proc/{pid}/stat", "r") as f:
                content = f.read()
                parts = content.split()
                if len(parts) >= 4:
                    return int(parts[3])
        except Exception:
            return -1
        return -1

    def _parse_name(self, pid):
        """Try to parse process name from /proc/[pid]/comm"""
        import os

        try:
            with open(f"/proc/{pid}/comm", "r") as f:
                return f.read().strip()
        except Exception:
            return None
        return None

    def _parse_cmd_line(self, pid):
        """Try to parse process cmdline from /proc/[pid]/cmdline"""
        try:
            with open(f"/proc/{pid}/cmdline", "r") as f:
                return f.read().replace("\x00", " ").strip()
        except Exception:
            return None
        return None

    @property
    def cmd_line_abbr(self, max_len=30):
        if self.cmdline and len(self.cmdline) > max_len:
            return self.cmdline[: max_len - 3] + "..."
        return self.cmdline

    @property
    def alive(self) -> bool:
        """Check if the process is still alive by checking /proc/[pid] existence"""
        return os.path.exists(f"/proc/{self.pid}")


class ThreadEntity(Entity):
    """
    Entity representing a thread node
    """

    tid: int = field(default_factory=lambda: -1)
    process: ProcessEntity | None = field(default=None)
    name: Optional[str] = field(default_factory=lambda: None)

    def __post_init__(self):
        if self.process is None:
            self.process = ProcessEntity()
        if isinstance(self.process, dict):
            self.process = ProcessEntity.create_ensure_unique_id(**self.process)
        # light weight process
        if self.name is None and self.tid > 0:
            self.name = self._parse_name(self.tid)
        super().__post_init__()

    @property
    def unique_id(self) -> str:
        return f"tid={self.tid}"

    def _cachable_str(self) -> str:
        return f"Thread(pid={self.process.pid},tid={self.tid},name={self.name})"

    def _parse_name(self, pid):
        """Try to parse process name from /proc/[pid]/comm"""
        import os

        try:
            with open(f"/proc/{pid}/comm", "r") as f:
                return f.read().strip()
        except Exception:
            return None
        return None


class SocketEntity(Entity):
    """
    Entity representing a socket node
    """

    socket_type: str = field(default=CONNECTION_TYPE_TCP)
    socket_addr: str = field(default_factory=lambda: "socket-addr-unknown")
    socket_port: int = field(default_factory=lambda: -1)
    socket_thread: ThreadEntity | None = field(default=None)
    socket_process: ProcessEntity | None = field(default=None)

    @property
    def unique_id(self) -> str:
        return f"{self.socket_addr}:{self.socket_port}({self.socket_type})"

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.socket_process, dict):
            self.socket_process = ProcessEntity.create_ensure_unique_id(
                **self.socket_process
            )
        if isinstance(self.socket_thread, dict):
            self.socket_thread = ThreadEntity.create_ensure_unique_id(
                **self.socket_thread
            )


class PipeInodeEntity(Entity):
    """
    Entity representing a pipe node
    """


class PodEntity(Entity):
    """
    Entity representing a pod node
    """

    pod_id: str = field(default_factory=lambda: "pod-id-unknown")

    @property
    def unique_id(self) -> str:
        return self.pod_id


class ContainerEntity(Entity):
    """
    Entity representing a container node
    """

    container_id: str = field(default_factory=lambda: "container-id-unknown")
    container_name: str = field(default_factory=lambda: "container-name-unknown")

    container_type: str = field(
        default_factory=lambda: "unknown"
    )  # e.g., docker, containerd, CRIO, unknown

    @property
    def unique_id(self) -> str:
        return self.container_id

    def __post_init__(self) -> None:
        super().__post_init__()
        self.container_id = str(self.container_id)[:8]  # Shorten for readability


__all__ = [
    "ProcessEntity",
    "ThreadEntity",
    "SocketEntity",
    "PipeInodeEntity",
    "PodEntity",
    "ContainerEntity",
]
